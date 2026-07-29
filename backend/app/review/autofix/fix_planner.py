from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class FixType(str, Enum):
    SAFE = "safe"           # Format/structure fix, no content change
    ASSISTED = "assisted"   # Structural fix, user confirms
    AI_FIX = "ai_fix"       # AI rewrites content, user confirms
    MANUAL = "manual"       # Cannot auto-fix


class FixStatus(str, Enum):
    PENDING = "pending"
    PREVIEWED = "previewed"
    APPLIED = "applied"
    REVERTED = "reverted"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class FixAction:
    """A single planned fix action for an issue."""
    id: str = field(default_factory=lambda: str(uuid4()))
    issue_id: str = ""
    rule_id: str = ""
    fix_type: FixType = FixType.MANUAL
    title: str = ""
    description: str = ""
    original_text: str = ""
    patched_text: str = ""
    location: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    status: FixStatus = FixStatus.PENDING
    depends_on: list[str] = field(default_factory=list)  # IDs of fixes that must run first
    knowledge_pack: str = ""
    estimated_impact: str = ""  # "Critical", "High", "Medium", "Low"


@dataclass
class FixPlanResult:
    """
    A comprehensive fix plan for a review session.

    Note: Named FixPlanResult to avoid collision with the existing
    FixPlan dataclass in app.review.autofix.models, which tracks
    suggestion-level categorisation (safe_fixes / need_confirmation).
    This class works at the issue/action level for the API fix-plan endpoint.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    session_id: str = ""
    actions: list[FixAction] = field(default_factory=list)
    safe_actions: list[FixAction] = field(default_factory=list)
    assisted_actions: list[FixAction] = field(default_factory=list)
    ai_actions: list[FixAction] = field(default_factory=list)
    manual_actions: list[FixAction] = field(default_factory=list)
    total_fixable: int = 0
    estimated_score_gain: int = 0


class IssuePlanner:
    """
    Creates fix plans from lists of Issue objects (or duck-typed dicts).

    Named IssuePlanner to avoid collision with the existing FixPlanner in
    app.review.autofix.planner (which operates on Suggestion objects).
    """

    def create_plan(self, issues: list[Any], session_id: str = "") -> FixPlanResult:
        """Create a fix plan from a list of issues."""
        plan = FixPlanResult(session_id=session_id)

        for issue in issues:
            if not getattr(issue, "autofix_allowed", False):
                # Create manual action
                action = FixAction(
                    issue_id=getattr(issue, "id", ""),
                    rule_id=getattr(issue, "rule_id", ""),
                    fix_type=FixType.MANUAL,
                    title=f"Manual fix required: {getattr(issue, 'rule_id', '')}",
                    description=getattr(issue, "recommendation", ""),
                    confidence=0.0,
                )
                plan.actions.append(action)
                plan.manual_actions.append(action)
            else:
                # Create auto-fix action
                source = getattr(issue, "source", "rule")
                fix_type = FixType.AI_FIX if source == "ai" else FixType.SAFE

                evidence = getattr(issue, "evidence", None)
                original_text = getattr(evidence, "excerpt", "") if evidence else ""

                action = FixAction(
                    issue_id=getattr(issue, "id", ""),
                    rule_id=getattr(issue, "rule_id", ""),
                    fix_type=fix_type,
                    title=f"Fix: {getattr(issue, 'rule_id', '')}",
                    description=getattr(issue, "recommendation", ""),
                    original_text=original_text,
                    confidence=getattr(issue, "confidence", 100) / 100.0,
                    estimated_impact=self._get_impact(getattr(issue, "severity", None)),
                )
                plan.actions.append(action)

                if fix_type == FixType.SAFE:
                    plan.safe_actions.append(action)
                elif fix_type == FixType.AI_FIX:
                    plan.ai_actions.append(action)

        plan.total_fixable = (
            len(plan.safe_actions) + len(plan.assisted_actions) + len(plan.ai_actions)
        )
        plan.estimated_score_gain = self._estimate_gain(issues)
        return plan

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_impact(self, severity: Any) -> str:
        if severity is None:
            return "Low"
        sev_val = severity.value if hasattr(severity, "value") else str(severity)
        return {
            "critical": "Critical",
            "high": "High",
            "medium": "Medium",
            "low": "Low",
        }.get(sev_val, "Low")

    def _estimate_gain(self, issues: list[Any]) -> int:
        gains = {"critical": 15, "high": 10, "medium": 5, "low": 2}
        fixable = [i for i in issues if getattr(i, "autofix_allowed", False)]
        total = sum(
            gains.get(
                i.severity.value if hasattr(i.severity, "value") else str(i.severity),
                2,
            )
            for i in fixable
        )
        return min(total, 40)  # Cap at 40 points improvement

    def resolve_dependencies(self, plan: FixPlanResult) -> list[FixAction]:
        """Return an ordered list of actions respecting declared dependencies (topological sort)."""
        ordered: list[FixAction] = []
        seen: set[str] = set()

        def visit(action: FixAction) -> None:
            if action.id in seen:
                return
            seen.add(action.id)
            for dep_id in action.depends_on:
                dep = next((a for a in plan.actions if a.id == dep_id), None)
                if dep:
                    visit(dep)
            ordered.append(action)

        for action in plan.actions:
            visit(action)

        return ordered
