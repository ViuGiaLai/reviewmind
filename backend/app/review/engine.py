from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from ..config import settings
from .models import ReviewRequest, ReviewResult
from .packs import PackLoader
from .parser import FileParser
from .profiles import ProfileLoader
from .report import render_markdown
from .rule_engine import RulePipeline
from .scoring import ScoreEngine
from .scheduler import AIReviewScheduler

logger = logging.getLogger(__name__)


class ReviewEngine:
    def __init__(self, config_directory: Path | None = None, enable_ai: bool = True):
        config_directory = config_directory or Path(__file__).resolve().parents[2] / "config"
        self.profiles = ProfileLoader(config_directory)
        self.packs = PackLoader(config_directory / "packs" if config_directory else None)
        self.parser = FileParser()
        self.rules = RulePipeline()
        self.scoring = ScoreEngine()
        self.scheduler = AIReviewScheduler()
        self.enable_ai = enable_ai and settings.llm.enabled and settings.llm.has_any_key

        # Lazy-init AI reviewer (only if LLM keys are configured)
        self._ai_reviewer: Any = None

    def _get_ai_reviewer(self):
        """Lazy initialize the AI reviewer to avoid import errors when no LLM keys are set."""
        if self._ai_reviewer is None and self.enable_ai:
            try:
                from ..llm import AIReviewer
                self._ai_reviewer = AIReviewer()
            except Exception as e:
                logger.warning(f"AI reviewer initialization failed: {e}. AI review disabled.")
                self.enable_ai = False
        return self._ai_reviewer

    async def review_async(self, request: ReviewRequest) -> ReviewResult:
        import time
        start_time = time.perf_counter()

        document = self.parser.parse_text(request.text, request.filename, request.content_type)
        detected_profile_id = self.profiles.detect_profile_from_text(request.text)
        resolved_profile_id = request.profile_id if request.profile_id != "auto" else detected_profile_id
        profile = self.profiles.load(resolved_profile_id)
        categories = set(request.enabled_categories or profile.categories) & set(profile.categories)

        # Merge profile permissions with pack overrides
        merged_permissions = self.packs.get_merged_permissions(
            profile.permissions, request.pack_ids
        )
        # Apply pack config overrides
        pack_config = self.packs.get_pack_config(request.pack_ids)

        # Create a patched profile with merged permissions so rules can use them
        from dataclasses import replace
        patched_profile = replace(profile, permissions=merged_permissions)

        # Run rules with pack context and patched permissions
        rule_start_time = time.perf_counter()
        issues = self.rules.run(
            document=document,
            profile=patched_profile,
            categories=categories,
            pack_ids=request.pack_ids,
            config_overrides=pack_config,
        )
        rule_duration_ms = (time.perf_counter() - rule_start_time) * 1000

        # ── AI Review Integration ────────────────────────────────────────────
        ai_review_enabled = False
        ai_review_reason = "AI review not evaluated."

        if self.enable_ai:
            try:
                decision = self.scheduler.decide(
                    document_text=request.text,
                    profile=profile,
                    issues=issues,
                    categories=categories,
                    pack_config=pack_config,
                )
                ai_review_enabled = decision.should_run
                ai_review_reason = decision.reason

                if decision.should_run:
                    ai_reviewer = self._get_ai_reviewer()
                    if ai_reviewer:
                        ai_issues = await ai_reviewer.analyze_document(
                            document_text=request.text,
                            profile=profile,
                            existing_issues=issues,
                            pack_info=pack_config,
                        )
                        if ai_issues:
                            logger.info(f"AI review found {len(ai_issues)} additional issues")
                            issues.extend(ai_issues)
                    else:
                        ai_review_enabled = False
                        ai_review_reason = "AI reviewer initialization failed."
                else:
                    logger.info("AI review skipped: %s", decision.reason)
            except Exception as e:
                logger.warning(f"AI review failed (non-fatal): {e}")
                ai_review_enabled = False
                ai_review_reason = f"AI review error: {e}"

        score, category_scores = self.scoring.score(issues, profile)
        total_duration_ms = (time.perf_counter() - start_time) * 1000

        # ── Compute Rich Metadata ─────────────────────────────────────────────
        from .models import BlockType
        paras = len([b for b in document.blocks if b.type == BlockType.PARAGRAPH]) or len([p for p in document.text.split("\n\n") if p.strip()])
        words = len(document.text.split())
        doc_stats = {
            "pages": document.metadata.page_count or len(document.pages) or max(1, words // 300),
            "paragraphs": paras,
            "headings": len(document.headings),
            "tables": len(document.tables),
            "figures": len(document.figures),
            "words": words,
            "references": len(document.references) or len(document.citations),
            "chars": len(document.text),
        }

        all_category_rules = [r for r in self.rules.registry._rules.values() if not categories or r.meta.category in categories]
        rules_loaded_count = len(all_category_rules)
        rule_issue_ids = set(i.rule_id for i in issues if i.source != "ai")
        failed_count = len(rule_issue_ids)
        passed_count = max(0, rules_loaded_count - failed_count)

        rule_stats = {
            "loaded": rules_loaded_count,
            "passed": passed_count,
            "failed": failed_count,
            "skipped": 0,
            "execution_ms": round(rule_duration_ms, 2),
        }

        autofix_count = sum(1 for i in issues if i.autofix_allowed)
        pipeline_status = {
            "parser": {"status": "completed", "label": f"{document.content_type or 'Text'} Parsed"},
            "profile": {"status": "completed", "label": profile.name},
            "knowledge_pack": {"status": "completed", "label": f"{len(request.pack_ids)} Pack(s)" if request.pack_ids else "Base Pack"},
            "rule_engine": {"status": "completed", "label": f"{rules_loaded_count} Rules Executed"},
            "ai_scheduler": {"status": "completed" if ai_review_enabled else "skipped", "label": ai_review_reason},
            "autofix": {"status": "ready" if autofix_count > 0 else "none", "label": f"{autofix_count} Fixes Available"},
        }

        return ReviewResult(
            profile_id=profile.id,
            pack_ids=request.pack_ids,
            issues=issues,
            score=score,
            category_scores=category_scores,
            summary=f"Found {len(issues)} issue(s) across {len(categories)} enabled category/categories.",
            report_markdown=render_markdown(profile.id, score, issues),
            ai_review_enabled=ai_review_enabled,
            ai_review_reason=ai_review_reason,
            duration_ms=round(total_duration_ms, 2),
            doc_stats=doc_stats,
            rule_stats=rule_stats,
            pipeline_status=pipeline_status,
            detected_profile=detected_profile_id,
        )

    def review(self, request: ReviewRequest) -> ReviewResult:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(lambda: asyncio.run(self.review_async(request)))
                return future.result()

        return asyncio.run(self.review_async(request))
