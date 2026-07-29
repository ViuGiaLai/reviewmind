from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AISchedulingDecision:
    should_run: bool
    reason: str
    required_capabilities: tuple[str, ...] = ()


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

        if not any(getattr(issue, "category", "") in {"writing", "logic", "summary"} for issue in issues):
            return AISchedulingDecision(False, self._default_reason, ())

        if not permissions.get("rewrite", 0) and not permissions.get("explain", 0):
            return AISchedulingDecision(False, "Profile does not allow AI-assisted explanation or rewrite actions.", ())

        if len(document_text.split()) < 80:
            return AISchedulingDecision(False, "Document is too short for AI review to add value.", ())

        return AISchedulingDecision(
            True,
            "Document contains high-value writing or logic issues that can benefit from AI assistance.",
            ("rewrite", "explain"),
        )
