from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..review.models import Evidence, Issue, ReviewResult, Severity
from .context import context_builder, ContextBuilder
from .guardrails import guardrails
from .prompts import prompt_registry
from .router import LLMRouter
from .validation import validator

logger = logging.getLogger(__name__)


@dataclass
class AIReviewStats:
    """Track AI review performance and costs."""
    total_reviews: int = 0
    total_issues_found: int = 0
    tokens_used: int = 0
    total_latency_ms: float = 0.0
    provider_usage: dict[str, int] = field(default_factory=dict)
    guardrail_blocks: int = 0
    errors: int = 0


class AIReviewer:
    """Integrates LLM-based analysis into the review pipeline.

    Provides:
    - AI-powered document analysis (detects issues rules cannot)
    - Issue explanation with rule references
    - Report summarization
    - QA on reviewed documents
    - Autofix suggestions with AI context
    """

    def __init__(
        self,
        router: LLMRouter | None = None,
        ctx_builder: ContextBuilder | None = None,
    ):
        self.router = router or LLMRouter()
        self.ctx_builder = ctx_builder or context_builder
        self.stats = AIReviewStats()

    # ── AI Review Pipeline ──────────────────────────────────────────────────

    async def analyze_document(
        self,
        document_text: str,
        profile: Any,
        existing_issues: list[Issue] | None = None,
        pack_info: dict[str, Any] | None = None,
        preferred_provider: str | None = None,
    ) -> list[Issue]:
        """Perform AI-powered analysis on a document and return discovered issues.

        This is designed to COMPLEMENT the rule engine by finding issues
        that rule-based checks cannot detect (tone, argument strength, etc.).
        """
        # Apply safety guardrails
        profile_id = getattr(profile, "id", "")
        guardrail_result = guardrails.validate_review_request(
            provider_name=preferred_provider or "auto",
            profile_id=profile_id,
            document_text=document_text,
        )

        if not guardrail_result.allowed:
            self.stats.guardrail_blocks += 1
            logger.warning(f"Guardrail blocked AI review: {guardrail_result.reason}")
            return []

        # Build context dict
        profile_name = getattr(profile, "name", getattr(profile, "id", "unknown"))
        pack_names = list(pack_info.keys()) if pack_info else []
        ctx = self.ctx_builder.build_review_context(
            document_text=document_text,
            profile_name=profile_name,
            pack_names=pack_names,
            existing_issues=[
                {"severity": i.severity.value, "rule_id": i.rule_id, "message": i.message}
                for i in (existing_issues or [])
            ],
        )

        # Check if document is too long - use chunked approach
        if len(document_text) > 6000:
            return await self._analyze_chunked(ctx, profile, preferred_provider)
        else:
            return await self._analyze_single(ctx, profile, preferred_provider)

    async def _analyze_single(
        self,
        ctx: dict[str, Any],
        profile: Any,
        preferred_provider: str | None = None,
    ) -> list[Issue]:
        """Analyze a document in a single pass."""
        try:
            profile_name = getattr(profile, "name", getattr(profile, "id", "unknown"))

            # Render prompt using registry
            system_prompt, user_prompt = prompt_registry.render(
                "review.full",
                profile=profile_name,
                packs=ctx.get("packs", ""),
                categories=ctx.get("categories", ""),
                document_text=ctx.get("document_text", ""),
                existing_issues=ctx.get("existing_issues", "None"),
            )

            # Call LLM via router
            response = await self.router.route(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )

            if not response.success or not response.response:
                logger.warning(f"AI review routing failed: {response.error}")
                return []

            llm_resp = response.response

            # Track stats
            self.stats.total_reviews += 1
            self.stats.tokens_used += (llm_resp.usage_input_tokens + llm_resp.usage_output_tokens)
            self.stats.total_latency_ms += llm_resp.latency_ms
            self.stats.provider_usage[llm_resp.provider] = (
                self.stats.provider_usage.get(llm_resp.provider, 0) + 1
            )

            # Parse and validate response
            parsed = validator.extract_json(llm_resp.text)
            if not parsed:
                logger.warning("AI review: no valid JSON found in response")
                return []

            validation = validator.validate_issues(parsed)
            if not validation.valid:
                logger.warning(f"AI review validation errors: {validation.errors}")
                return []

            # Convert to Issue objects
            issues = []
            now_ts = datetime.now(timezone.utc).timestamp()
            for item in validation.parsed:
                issue = Issue(
                    id=f"ai-{now_ts}-{len(issues)}",
                    category=item.get("category", "writing"),
                    rule_id=item.get("rule_id", "ai.general"),
                    severity=Severity(item.get("severity", "medium")),
                    message=item.get("message", ""),
                    recommendation=item.get("recommendation", ""),
                    evidence=Evidence(
                        excerpt=item.get("evidence_excerpt", ""),
                        line_start=0,
                        line_end=0,
                        location="AI analysis",
                    ),
                    confidence=int(item.get("confidence", 50)),
                    source="ai",
                    autofix_allowed=False,
                )
                issues.append(issue)

            self.stats.total_issues_found += len(issues)
            logger.info(f"AI review found {len(issues)} issues via {llm_resp.provider}")
            return issues

        except Exception as e:
            self.stats.errors += 1
            logger.error(f"AI review failed: {e}", exc_info=True)
            return []

    async def _analyze_chunked(
        self,
        base_ctx: dict[str, Any],
        profile: Any,
        preferred_provider: str | None = None,
    ) -> list[Issue]:
        """Analyze a long document by processing chunks."""
        all_issues: list[Issue] = []
        document_text = base_ctx.get("document_text", "")

        # Build chunked contexts using the chunking engine
        from .chunking import chunking_engine

        chunks = chunking_engine.chunk_text(
            document_text,
            chunk_size=4000,
            chunk_overlap=300,
            respect_boundaries=True,
        )

        logger.info(f"AI review: processing {len(chunks)} chunks")

        for i, chunk in enumerate(chunks):
            logger.info(f"AI review chunk {i + 1}/{len(chunks)}")
            chunk_ctx = dict(base_ctx)
            chunk_ctx["document_text"] = chunk.text
            chunk_ctx["existing_issues"] = f"chunk {i + 1} of {len(chunks)}"

            chunk_issues = await self._analyze_single(chunk_ctx, profile, preferred_provider)
            all_issues.extend(chunk_issues)

        logger.info(f"AI review complete: {len(all_issues)} issues from {len(chunks)} chunks")
        return all_issues

    # ── Other AI Features ───────────────────────────────────────────────────

    async def explain_issue(
        self,
        issue: Issue,
        rule_context: str = "",
        document_excerpt: str = "",
    ) -> str:
        """Generate a detailed explanation of an issue with rule references."""
        try:
            system_prompt, user_prompt = prompt_registry.render(
                "explain.issue",
                message=issue.message,
                category=issue.category,
                rule_id=issue.rule_id,
                severity=issue.severity.value,
                evidence=issue.evidence.excerpt or document_excerpt[:2000],
                recommendation=issue.recommendation,
                profile="academic",
            )

            response = await self.router.route(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )

            if response.success and response.response:
                return response.response.text
            return f"Explanation unavailable: {response.error}"

        except Exception as e:
            logger.error(f"AI explain failed: {e}")
            return f"Explanation unavailable: {e}"

    async def summarize_report(
        self,
        result: ReviewResult,
    ) -> str:
        """Generate an executive summary of a review report."""
        try:
            top_issues = "\n".join(
                f"- [{i.severity.value}] {i.message}"
                for i in result.issues[:5]
            )

            system_prompt, user_prompt = prompt_registry.render(
                "summary.review",
                score=str(result.score),
                issue_count=str(len(result.issues)),
                category_scores=json.dumps(result.category_scores, indent=2),
                top_issues=top_issues,
            )

            response = await self.router.route(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )

            if response.success and response.response:
                return response.response.text
            return result.summary  # Fall back to rule-based summary

        except Exception as e:
            logger.error(f"AI summarize failed: {e}")
            return result.summary

    async def suggest_autofix(
        self,
        issue: Issue,
        document_excerpt: str,
        profile_rules: str = "",
    ) -> dict[str, str] | None:
        """Generate an AI-powered fix suggestion for a specific issue."""
        try:
            system_prompt, user_prompt = prompt_registry.render(
                "fix.suggest",
                category=issue.category,
                rule_id=issue.rule_id,
                text=document_excerpt[:3000],
                recommendation=issue.recommendation,
            )

            response = await self.router.route(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )

            if not response.success or not response.response:
                return None

            parsed = validator.extract_json(response.response.text)
            if parsed and len(parsed) > 0:
                fix_data = parsed[0]
                vr = validator.validate_fix(fix_data)
                if vr.valid:
                    return fix_data

            return None

        except Exception as e:
            logger.error(f"AI autofix suggestion failed: {e}")
            return None

    async def answer_question(
        self,
        question: str,
        document_context: str = "",
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        """Answer a user's question about the reviewed document."""
        try:
            system_prompt = "You are a document analysis assistant. Answer questions based on the provided document context."
            user_prompt = (
                f"Document Context:\n{document_context[:4000]}\n\n"
                f"Question: {question}\n\n"
                f"Conversation History: {json.dumps(conversation_history or [])}"
            )

            response = await self.router.route(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )

            if response.success and response.response:
                return response.response.text
            return f"Unable to answer: {response.error}"

        except Exception as e:
            logger.error(f"AI QA failed: {e}")
            return f"Unable to answer: {e}"

    def get_router_stats(self) -> dict[str, Any]:
        """Get router usage statistics."""
        return self.router.get_stats()

    def reset_stats(self) -> None:
        """Reset all statistics."""
        self.stats = AIReviewStats()
        self.router.reset_stats()


# Global instance
ai_reviewer = AIReviewer()
