from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AISchedulingDecision:
    should_run: bool
    reason: str
    required_capabilities: tuple[str, ...] = ()
    evaluation_types: tuple[str, ...] = ()


class AIReviewScheduler:
    """Decide whether an AI review is appropriate for a given document and issue set.

    The backend should be rule-first and AI-optional. Most checks run through the
    rule engine; AI is only used for high-value writing, reasoning, or explanation
    tasks when the profile and content justify it.
    """

    def __init__(self) -> None:
        self._default_reason = "Rule engine handled the review successfully; AI review skipped."

    def decide(
        self,
        document_text: str,
        profile: Any,
        issues: list[Any],
        categories: set[str],
        pack_config: dict[str, Any],
    ) -> AISchedulingDecision:
        profile_id = getattr(profile, "id", "") or ""
        permissions = getattr(profile, "permissions", {}) or {}

        if not document_text.strip():
            return AISchedulingDecision(False, "Document is empty.", ())

        if profile_id == "sop" and "writing" in categories:
            return AISchedulingDecision(False, "SOP profiles disable AI-assisted rewriting and writing enhancement.", ())

        semantic_categories = {"writing", "logic", "summary", "technical"}
        ai_focus = tuple(getattr(profile, "ai_focus", ()) or ())
        has_semantic_issue = any(
            getattr(issue, "category", "") in semantic_categories for issue in issues
        )
        has_semantic_scope = bool(categories & semantic_categories) or bool(ai_focus)
        if not has_semantic_issue and not has_semantic_scope:
            return AISchedulingDecision(False, self._default_reason, ())

        # Permission levels are category based: 1=detect, 2=explain,
        # 3=suggest, 4=rewrite, 5=autofix.
        allowed_levels = [
            int(permissions.get(category, 0) or 0)
            for category in (categories & semantic_categories)
        ]
        if allowed_levels and max(allowed_levels) < 2:
            return AISchedulingDecision(False, "Profile does not allow AI-assisted explanation or rewrite actions.", ())

        if len(document_text.split()) < 80:
            return AISchedulingDecision(False, "Document is too short for AI review to add value.", ())

        return AISchedulingDecision(
            True,
            "Document contains high-value writing or logic issues that can benefit from AI assistance.",
            ("detect", "explain"),
            ai_focus or tuple(sorted(categories & semantic_categories)),
        )
