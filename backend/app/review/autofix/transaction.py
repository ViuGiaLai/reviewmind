from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Iterable
from uuid import NAMESPACE_URL, uuid5

from .diff_generator import DiffGenerator, DiffResult
from .models import FixApplyResult, Suggestion


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_suggestion_id(session_id: str, suggestion: Suggestion) -> str:
    """Create a stable ID so preview/apply/history refer to the same suggestion."""
    identity = "|".join([
        session_id,
        suggestion.issue_id,
        suggestion.rule_id,
        str(suggestion.line_start),
        str(suggestion.line_end),
        suggestion.original_text,
        suggestion.suggested_text,
    ])
    return str(uuid5(NAMESPACE_URL, f"reviewmind:autofix:{identity}"))


@dataclass(frozen=True)
class FixConflict:
    winner_id: str
    blocked_id: str
    reason: str


@dataclass
class FixPreview:
    suggestion_id: str
    before_hash: str
    after_hash: str
    diff: DiffResult
    confidence: int
    fix_type: str
    requires_confirmation: bool
    explanation: str
    conflicts: list[FixConflict] = field(default_factory=list)


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    reason: str
    before_hash: str
    after_hash: str


class AutoFixTransactionEngine:
    """Apply exact, previewed and reversible text transactions."""

    _FIX_PRIORITY = {"safe": 3, "assisted": 2, "ai": 1, "manual": 0}

    def __init__(self) -> None:
        self.diff_generator = DiffGenerator()

    def preview(self, text: str, suggestion: Suggestion) -> FixPreview:
        result = self.apply(text, suggestion)
        patched = result.patched_text if result.success else text
        return FixPreview(
            suggestion_id=suggestion.id,
            before_hash=text_hash(text),
            after_hash=text_hash(patched),
            diff=self.diff_generator.generate_diff(text, patched),
            confidence=suggestion.confidence,
            fix_type=suggestion.fix_type,
            requires_confirmation=suggestion.fix_type != "safe" or suggestion.confidence < 95,
            explanation=suggestion.message,
        )

    def apply(self, text: str, suggestion: Suggestion) -> FixApplyResult:
        if suggestion.applied:
            return FixApplyResult(success=False, error="Suggestion already applied.")
        if not suggestion.original_text:
            return FixApplyResult(success=False, error="Suggestion has no source text.")
        if suggestion.original_text == suggestion.suggested_text:
            return FixApplyResult(success=False, error="Suggestion does not change the document.")

        located = self._locate_exact(text, suggestion)
        if isinstance(located, str):
            return FixApplyResult(success=False, error=located)
        start, end = located
        patched = text[:start] + suggestion.suggested_text + text[end:]
        verification = self.verify(text, patched, suggestion, start)
        if not verification.passed:
            return FixApplyResult(success=False, error=verification.reason)
        return FixApplyResult(success=True, patched_text=patched, changes=1)

    def revert(self, text: str, suggestion: Suggestion) -> FixApplyResult:
        if not suggestion.applied:
            return FixApplyResult(success=False, error="Suggestion has not been applied.")
        reverse = Suggestion(
            id=suggestion.id,
            original_text=suggestion.suggested_text,
            suggested_text=suggestion.original_text,
            line_start=suggestion.line_start,
            line_end=suggestion.line_end + suggestion.suggested_text.count("\n"),
        )
        return self.apply(text, reverse)

    def verify(
        self,
        before: str,
        after: str,
        suggestion: Suggestion,
        replacement_offset: int,
    ) -> VerificationResult:
        before_digest = text_hash(before)
        after_digest = text_hash(after)
        expected = (
            before[:replacement_offset]
            + suggestion.suggested_text
            + before[replacement_offset + len(suggestion.original_text):]
        )
        if before_digest == after_digest:
            return VerificationResult(False, "Fix produced no change.", before_digest, after_digest)
        if after != expected:
            return VerificationResult(
                False, "Fix changed content outside the approved range.", before_digest, after_digest
            )
        return VerificationResult(True, "Exact replacement verified.", before_digest, after_digest)

    def resolve_conflicts(
        self, suggestions: Iterable[Suggestion]
    ) -> tuple[list[Suggestion], list[FixConflict]]:
        ordered = sorted(
            suggestions,
            key=lambda item: (
                self._FIX_PRIORITY.get(item.fix_type, 0),
                item.confidence,
                -item.line_start,
            ),
            reverse=True,
        )
        accepted: list[Suggestion] = []
        conflicts: list[FixConflict] = []
        for candidate in ordered:
            winner = next((item for item in accepted if self._overlaps(item, candidate)), None)
            if winner:
                conflicts.append(FixConflict(
                    winner_id=winner.id,
                    blocked_id=candidate.id,
                    reason="Suggestions modify overlapping source ranges.",
                ))
            else:
                accepted.append(candidate)
        # Descending locations prevent earlier edits from shifting later ranges.
        accepted.sort(key=lambda item: (item.line_start, item.line_end), reverse=True)
        return accepted, conflicts

    def _locate_exact(self, text: str, suggestion: Suggestion) -> tuple[int, int] | str:
        lines = text.splitlines(keepends=True)
        line_start = max(1, suggestion.line_start)
        line_end = max(line_start, suggestion.line_end)
        range_start = sum(len(line) for line in lines[:line_start - 1])
        range_end = sum(len(line) for line in lines[:line_end])
        if not lines:
            range_end = len(text)
        window = text[range_start:range_end]
        relative = window.find(suggestion.original_text)
        if relative >= 0 and window.count(suggestion.original_text) == 1:
            start = range_start + relative
            return start, start + len(suggestion.original_text)

        count = text.count(suggestion.original_text)
        if count == 0:
            return "Source text changed after preview; regenerate the suggestion."
        if count > 1:
            return "Source text is ambiguous; exact location confirmation is required."
        start = text.find(suggestion.original_text)
        return start, start + len(suggestion.original_text)

    @staticmethod
    def _overlaps(left: Suggestion, right: Suggestion) -> bool:
        return not (left.line_end < right.line_start or right.line_end < left.line_start)
