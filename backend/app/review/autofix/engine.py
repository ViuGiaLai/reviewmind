from __future__ import annotations

import difflib
import re
from typing import Any
from uuid import uuid4

from .models import Suggestion, DiffLine, FixApplyResult, FixPlan, ChangeSummary
from .diff_engine import DiffEngine
from .fix_confidence import FixConfidenceCalculator
from .planner import FixPlanner
from .safe_rules import SafeFixRules
from .transaction import AutoFixTransactionEngine, stable_suggestion_id


class SuggestionEngine:
    """Core engine for generating, applying, and reverting auto-fix suggestions."""

    def __init__(self):
        self.diff_engine = DiffEngine()
        self.confidence_calculator = FixConfidenceCalculator()
        self.planner = FixPlanner()
        self.safe_rules = SafeFixRules()
        self.transaction = AutoFixTransactionEngine()

    def generate_suggestions(
        self,
        text: str,
        issues: list[Any],
        session_id: str,
    ) -> list[Suggestion]:
        """Generate auto-fix suggestions from a list of issues."""
        suggestions: list[Suggestion] = []
        lines = text.split("\n")

        for issue in issues:
            autofix_allowed = getattr(issue, "autofix_allowed", 0)
            if not autofix_allowed:
                continue

            original_text = ""
            line_start = getattr(issue, "evidence_line_start", 1)
            line_end = getattr(issue, "evidence_line_end", 1)

            # Try to get the original text from the document
            if hasattr(issue, "evidence") and issue.evidence:
                original_text = issue.evidence.excerpt
                line_start = issue.evidence.line_start
                line_end = issue.evidence.line_end
            elif hasattr(issue, "evidence_excerpt") and issue.evidence_excerpt:
                original_text = issue.evidence_excerpt
            elif line_start <= len(lines):
                original_text = "\n".join(lines[max(0, line_start - 1):min(len(lines), line_end)])
            elif issue.message:
                original_text = issue.message

            if not original_text or not original_text.strip():
                continue

            # Generate suggested fix based on rule
            suggested_text = self._generate_fix(
                original_text,
                getattr(issue, "rule_id", ""),
                getattr(issue, "category", ""),
            )

            if not suggested_text or suggested_text == original_text:
                continue

            rule_id = getattr(issue, "rule_id", "")
            severity = getattr(issue, "severity", "low")
            if hasattr(severity, "value"):
                severity = severity.value
            category = getattr(issue, "category", "")
            message = getattr(issue, "message", "")
            recommendation = getattr(issue, "recommendation", "")
            confidence_val = getattr(issue, "confidence", 50)

            suggestion = Suggestion(
                issue_id=getattr(issue, "id", getattr(issue, "issue_id", "")),
                rule_id=rule_id,
                severity=str(severity),
                message=message or f"Fix {rule_id.replace('-', ' ')} issue",
                original_text=original_text,
                suggested_text=suggested_text,
                line_start=line_start,
                line_end=line_end,
                confidence=confidence_val,
                category=category,
                fix_type=self._determine_fix_type(rule_id, category),
            )
            suggestion.id = stable_suggestion_id(session_id, suggestion)
            suggestions.append(suggestion)

        return suggestions

    def _generate_fix(self, text: str, rule_id: str, category: str) -> str | None:
        """Generate a fix for a specific rule."""
        normalized_rule_id = rule_id.casefold().replace("_", "-").rsplit(".", 1)[-1]
        # Safe format fixes
        if normalized_rule_id == "heading-numbering":
            return SafeFixRules.fix_heading_style(text)
        elif normalized_rule_id == "line-spacing":
            return SafeFixRules.fix_line_spacing(text)
        elif normalized_rule_id == "reference-formatting" or "reference" in normalized_rule_id:
            return SafeFixRules.fix_reference_formatting(text)
        elif normalized_rule_id == "broken-hyperlinks" or "url" in normalized_rule_id:
            return SafeFixRules.fix_http_prefix(text)
        elif normalized_rule_id == "bullet-list":
            return SafeFixRules.fix_bullet_consistency(text)
        elif normalized_rule_id in {"punctuation", "period-spacing"}:
            return SafeFixRules.fix_period_spacing(text)
        elif "citation-order" in normalized_rule_id:
            return SafeFixRules.fix_citation_order(text)

        # Category-based generic fixes
        if category == "grammar" or normalized_rule_id == "spelling":
            return self._fix_spelling(text)
        elif category == "writing" and "passive" in normalized_rule_id:
            return self._fix_passive_voice(text)
        elif category == "writing" and "hedging" in normalized_rule_id:
            return self._fix_hedging(text)
        elif category == "format":
            return SafeFixRules.fix_period_spacing(text)

        # Recommendation-based fix
        return None

    def _fix_spelling(self, text: str) -> str:
        """Fix common spelling mistakes."""
        corrections = {
            r"\bteh\b": "the",
            r"\brecieve\b": "receive",
            r"\bacheive\b": "achieve",
            r"\bbeleive\b": "believe",
            r"\bdefinately\b": "definitely",
            r"\boccured\b": "occurred",
            r"\boccuring\b": "occurring",
            r"\baccomodate\b": "accommodate",
            r"\bembarass\b": "embarrass",
            r"\bindependent\b": "independent",
            r"\bjudgment\b": "judgement",
            r"\blaboratory\b": "laboratory",
            r"\bliason\b": "liaison",
            r"\bmaintainance\b": "maintenance",
            r"\bminiscule\b": "minuscule",
            r"\bneccessary\b": "necessary",
            r"\boccassion\b": "occasion",
            r"\brepetition\b": "repetition",
            r"\bseparate\b": "separate",
            r"\bsupercede\b": "supersede",
            r"\btomorrow\b": "tomorrow",
            r"\bcalender\b": "calendar",
            r"\bheirarchy\b": "hierarchy",
            r"\bgoverment\b": "government",
            r"\bpriviledge\b": "privilege",
            r"\bpublically\b": "publicly",
            r"\btruely\b": "truly",
            r"\bwierd\b": "weird",
        }
        for pattern, replacement in corrections.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    def _fix_passive_voice(self, text: str) -> str:
        """Simple passive voice detection (mark rather than fix)."""
        # For passive voice, return the text with a note - AI would handle this
        return text

    def _fix_hedging(self, text: str) -> str:
        """Remove common hedging words."""
        hedging_words = [
            (r"\barguably\b", ""),
            (r"\bquite\b", ""),
            (r"\brather\b", ""),
            (r"\bsomewhat\b", ""),
            (r"\bpossibly\b", ""),
            (r"\bperhaps\b", "maybe"),
            (r"\bseems to\b", "appears to"),
            (r"\btends to be\b", "is typically"),
        ]
        result = text
        for pattern, replacement in hedging_words:
            if replacement:
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
            else:
                # Remove the word but keep the space intact
                result = re.sub(pattern + r"\s*", " ", result, flags=re.IGNORECASE)
        return result

    def _determine_fix_type(self, rule_id: str, category: str) -> str:
        """Determine whether a fix is safe, AI, or manual."""
        normalized_rule_id = rule_id.casefold().replace("_", "-").rsplit(".", 1)[-1]
        safe_rules = {
            "heading-numbering", "heading-hierarchy", "font-size", "line-spacing",
            "paragraph-spacing", "margin", "page-number", "header", "footer",
            "caption-numbering", "figure-numbering", "table-numbering",
            "bullet-list", "numbered-list", "period-spacing",
            "reference-formatting", "broken-hyperlinks",
        }
        ai_rules = {
            "passive-voice", "grammar", "spelling", "punctuation",
            "weak-wording", "hedging", "repetition",
            "tone-consistency", "readability",
        }
        if normalized_rule_id in safe_rules:
            return "safe"
        elif normalized_rule_id in ai_rules:
            return "ai"
        else:
            return "manual"

    def generate_diff(self, original: str, suggested: str) -> list[DiffLine]:
        """Generate a diff between original and suggested text."""
        return self.diff_engine.line_diff(original, suggested)

    def preview_suggestion(self, text: str, suggestion: Suggestion):
        """Generate the mandatory before/after preview without mutating state."""
        return self.transaction.preview(text, suggestion)

    def apply_suggestion(self, text: str, suggestion: Suggestion) -> FixApplyResult:
        """Apply one exact, verified replacement."""
        return self.transaction.apply(text, suggestion)
    def revert_suggestion(self, text: str, suggestion: Suggestion) -> FixApplyResult:
        """Undo one exact replacement."""
        return self.transaction.revert(text, suggestion)
    def apply_suggestions_bulk(
        self,
        text: str,
        suggestions: list[Suggestion],
    ) -> tuple[str, list[Suggestion], list[FixApplyResult]]:
        """Resolve overlaps, then apply a safe location-descending batch."""
        patched_text = text
        applied: list[Suggestion] = []
        results: list[FixApplyResult] = []
        accepted, conflicts = self.transaction.resolve_conflicts(suggestions)
        blocked = {conflict.blocked_id: conflict for conflict in conflicts}

        for suggestion in suggestions:
            if suggestion.id in blocked:
                results.append(FixApplyResult(
                    success=False,
                    error=f"Conflict: {blocked[suggestion.id].reason}",
                ))

        for suggestion in accepted:
            result = self.apply_suggestion(patched_text, suggestion)
            if result.success:
                patched_text = result.patched_text
                suggestion.applied = True
                applied.append(suggestion)
            results.append(result)
        return patched_text, applied, results
    def create_change_summary(self, suggestions: list[Suggestion]) -> ChangeSummary:
        """Create a summary of changes from suggestions."""
        summary = ChangeSummary()
        for s in suggestions:
            if s.applied:
                summary.total_applied += 1
                cat = s.category or "other"
                summary.by_category[cat] = summary.by_category.get(cat, 0) + 1
                rule = s.rule_id or "unknown"
                summary.by_rule[rule] = summary.by_rule.get(rule, 0) + 1
                sev = s.severity or "low"
                summary.by_severity[sev] = summary.by_severity.get(sev, 0) + 1
        return summary
