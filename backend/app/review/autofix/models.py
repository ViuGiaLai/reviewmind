from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class Suggestion:
    """A single autofix suggestion."""
    id: str = field(default_factory=lambda: str(uuid4()))
    issue_id: str = ""
    rule_id: str = ""
    severity: str = "low"
    message: str = ""
    original_text: str = ""
    suggested_text: str = ""
    line_start: int = 1
    line_end: int = 1
    confidence: int = 50  # 0-100
    category: str = ""
    fix_type: str = "safe"  # safe | ai | manual
    applied: bool = False
    applied_at: str | None = None
    reverted_at: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DiffLine:
    """A single line in a diff output."""
    type: str  # "same" | "added" | "removed" | "changed"
    old_line: int | None = None
    new_line: int | None = None
    old_text: str = ""
    new_text: str = ""


@dataclass
class FixApplyResult:
    """Result of applying a fix."""
    success: bool
    patched_text: str = ""
    changes: int = 0
    error: str | None = None


@dataclass
class FixConfidence:
    """Confidence rating for a fix suggestion."""
    score: int  # 0-100
    level: str = "medium"  # high | medium | low | suggestion
    label: str = ""  # "100% Safe", "98%", "86%", etc.
    reasons: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.label:
            if self.score >= 95:
                self.label = f"🟢 {self.score}% Safe"
                self.level = "high"
            elif self.score >= 80:
                self.label = f"🟢 {self.score}%"
                self.level = "high"
            elif self.score >= 60:
                self.label = f"🟡 {self.score}%"
                self.level = "medium"
            elif self.score >= 40:
                self.label = f"🟠 {self.score}%"
                self.level = "medium"
            else:
                self.label = f"🔴 Suggestion Only"
                self.level = "low"


@dataclass
class FixPlan:
    """Plan for fixing issues in a session."""
    total_issues: int = 0
    safe_fixes: int = 0      # Can auto-apply safely
    need_confirmation: int = 0  # Needs user review
    manual_only: int = 0     # Cannot auto-fix
    suggestions: list[Suggestion] = field(default_factory=list)
    estimated_time_seconds: int = 0
    estimated_success_rate: int = 95  # percent
    grouped_by_category: dict[str, int] = field(default_factory=dict)


@dataclass
class ChangeSummary:
    """Summary of applied changes."""
    total_applied: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_rule: dict[str, int] = field(default_factory=dict)
    by_severity: dict[str, int] = field(default_factory=dict)
    reverted_count: int = 0
