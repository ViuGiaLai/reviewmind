from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .models import FixPlan, Suggestion, FixConfidence
from .fix_confidence import FixConfidenceCalculator


class FixPlanner:
    """Plans and categorizes auto-fix suggestions."""

    def __init__(self):
        self.confidence_calculator = FixConfidenceCalculator()

    def create_plan(
        self,
        suggestions: list[Suggestion],
    ) -> FixPlan:
        """Create a fix plan from a list of suggestions."""
        safe: list[Suggestion] = []
        confirm: list[Suggestion] = []
        manual: list[Suggestion] = []
        categories: dict[str, int] = {}

        for s in suggestions:
            fix_type = self.confidence_calculator.categorize_fix_type(s)
            if fix_type == "safe":
                safe.append(s)
            elif fix_type == "confirm" or fix_type == "review":
                confirm.append(s)
            else:
                manual.append(s)

            cat = s.category or "other"
            categories[cat] = categories.get(cat, 0) + 1

        # Estimate time based on fix count and type
        total = len(suggestions)
        safe_time = len(safe) * 0.5  # 0.5 seconds per safe fix
        confirm_time = len(confirm) * 2  # 2 seconds per confirm fix
        manual_time = len(manual) * 5  # 5 seconds per manual fix
        estimated_seconds = int(safe_time + confirm_time + manual_time)

        # Estimate success rate
        if total > 0:
            success_rate = int((len(safe) * 99 + len(confirm) * 80 + len(manual) * 30) / total)
        else:
            success_rate = 95

        return FixPlan(
            total_issues=total,
            safe_fixes=len(safe),
            need_confirmation=len(confirm),
            manual_only=len(manual),
            suggestions=suggestions,
            estimated_time_seconds=estimated_seconds,
            estimated_success_rate=success_rate,
            grouped_by_category=categories,
        )
