from __future__ import annotations

from typing import Any

from ..models import Issue, Severity
from .models import (
    AutoFixCapability,
    IssueCategory,
    IssueSource,
    IssueSeverity,
    ReadinessLevel,
    UnifiedIssue,
)

# ─── Severity mapping: legacy Severity → IssueSeverity ────────────────────────
_SEVERITY_MAP: dict[str, IssueSeverity] = {
    "critical": IssueSeverity.CRITICAL,
    "high": IssueSeverity.HIGH,
    "medium": IssueSeverity.MEDIUM,
    "low": IssueSeverity.LOW,
}

# ─── Source mapping: issue.source str → IssueSource ───────────────────────────
_SOURCE_MAP: dict[str, IssueSource] = {
    "rule": IssueSource.RULE_ENGINE,
    "rule_engine": IssueSource.RULE_ENGINE,
    "ai": IssueSource.AI_REVIEW,
    "ai_review": IssueSource.AI_REVIEW,
    "cross_rule": IssueSource.CROSS_RULE,
    "compliance": IssueSource.COMPLIANCE,
}

# ─── Category mapping: issue.category str → IssueCategory ─────────────────────
_CATEGORY_MAP: dict[str, IssueCategory] = {
    "formatting": IssueCategory.FORMATTING,
    "structure": IssueCategory.STRUCTURE,
    "writing": IssueCategory.WRITING,
    "citation": IssueCategory.CITATION,
    "logic": IssueCategory.LOGIC,
    "compliance": IssueCategory.COMPLIANCE,
    "figures": IssueCategory.FIGURES,
    "tables": IssueCategory.TABLES,
    "consistency": IssueCategory.CONSISTENCY,
    "ai_finding": IssueCategory.AI_FINDING,
}


class IssueManager:
    """Manages a collection of UnifiedIssue objects: conversion, deduplication,
    dependency tracking, prioritization, and scoring readiness."""

    def __init__(self) -> None:
        self._issues: list[UnifiedIssue] = []

    # ─── Conversion helpers ────────────────────────────────────────────────

    def _map_severity(self, issue: Issue) -> IssueSeverity:
        sev_str = issue.severity.value if isinstance(issue.severity, Severity) else str(issue.severity)
        return _SEVERITY_MAP.get(sev_str.lower(), IssueSeverity.MEDIUM)

    def _map_source(self, issue: Issue) -> IssueSource:
        return _SOURCE_MAP.get(str(issue.source).lower(), IssueSource.RULE_ENGINE)

    def _map_category(self, issue: Issue) -> IssueCategory:
        return _CATEGORY_MAP.get(str(issue.category).lower(), IssueCategory.WRITING)

    def _map_autofix(self, issue: Issue) -> AutoFixCapability:
        """Map autofix_allowed flag to AutoFixCapability enum."""
        if issue.autofix_allowed:
            return AutoFixCapability.ASSISTED
        return AutoFixCapability.MANUAL

    def _build_location(self, issue: Issue) -> dict[str, Any]:
        """Extract location dict from an Issue's evidence."""
        try:
            ev = issue.evidence
            return {
                "line_start": ev.line_start,
                "line_end": ev.line_end,
                "page_number": getattr(ev, "page_number", 0),
                "location": getattr(ev, "location", ""),
            }
        except AttributeError:
            return {}

    # ─── Public API ───────────────────────────────────────────────────────

    def add_from_review_issue(self, issue: Issue) -> UnifiedIssue:
        """Convert a legacy Issue to UnifiedIssue and store it."""
        unified = UnifiedIssue(
            id=issue.id,
            category=self._map_category(issue),
            source=self._map_source(issue),
            severity=self._map_severity(issue),
            confidence=issue.confidence / 100.0 if issue.confidence > 1 else float(issue.confidence),
            title=issue.rule_id,
            description=issue.message,
            evidence=issue.evidence.excerpt if issue.evidence else "",
            recommendation=issue.recommendation,
            auto_fix_capability=self._map_autofix(issue),
            location=self._build_location(issue),
            rule_id=issue.rule_id,
        )
        self._issues.append(unified)
        return unified

    def add_issues_from_review(self, issues: list[Issue]) -> list[UnifiedIssue]:
        """Batch-convert a list of legacy Issues to UnifiedIssues."""
        return [self.add_from_review_issue(i) for i in issues]

    def deduplicate(self) -> int:
        """Remove duplicate issues based on rule_id + location.

        Returns the count of duplicates removed.
        """
        seen: set[str] = set()
        unique: list[UnifiedIssue] = []
        duplicates = 0

        for issue in self._issues:
            key = f"{issue.rule_id}:{issue.location.get('line_start', 0)}"
            if key in seen:
                duplicates += 1
                issue.is_duplicate = True
            else:
                seen.add(key)
                unique.append(issue)

        self._issues = unique
        return duplicates

    def build_dependency_graph(self) -> dict[str, list[str]]:
        """Build an issue dependency graph.

        Example cascade: Heading issue → TOC issue → Navigation issue.
        If a heading issue is fixed, related TOC issues should auto-resolve.
        """
        deps: dict[str, list[str]] = {}

        heading_issues = [i for i in self._issues if "heading" in i.rule_id.lower()]
        toc_issues = [i for i in self._issues if "toc" in i.rule_id.lower()]
        figure_issues = [
            i for i in self._issues
            if "figure" in i.rule_id.lower() or "caption" in i.rule_id.lower()
        ]

        for hi in heading_issues:
            deps[hi.id] = [ti.id for ti in toc_issues]

        # Figure → caption dependency
        caption_issues = [i for i in figure_issues if "caption" in i.rule_id.lower()]
        figure_only = [i for i in figure_issues if "figure" in i.rule_id.lower() and "caption" not in i.rule_id.lower()]
        for fi in figure_only:
            deps.setdefault(fi.id, []).extend([ci.id for ci in caption_issues])

        return deps

    def prioritize(self) -> list[UnifiedIssue]:
        """Sort issues by severity (Critical → Low) then fix ease (SAFE → MANUAL)."""
        severity_order = {
            IssueSeverity.CRITICAL: 0,
            IssueSeverity.HIGH: 1,
            IssueSeverity.MEDIUM: 2,
            IssueSeverity.LOW: 3,
        }
        fix_order = {
            AutoFixCapability.SAFE: 0,
            AutoFixCapability.ASSISTED: 1,
            AutoFixCapability.AI_FIX: 2,
            AutoFixCapability.MANUAL: 3,
        }
        return sorted(
            self._issues,
            key=lambda i: (
                severity_order.get(i.severity, 4),
                fix_order.get(i.auto_fix_capability, 4),
            ),
        )

    def get_summary(self) -> dict[str, Any]:
        """Return summary statistics across all issues."""
        issues = self._issues
        return {
            "total": len(issues),
            "critical": sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL),
            "high": sum(1 for i in issues if i.severity == IssueSeverity.HIGH),
            "medium": sum(1 for i in issues if i.severity == IssueSeverity.MEDIUM),
            "low": sum(1 for i in issues if i.severity == IssueSeverity.LOW),
            "auto_fixable": sum(
                1 for i in issues
                if i.auto_fix_capability in (AutoFixCapability.SAFE, AutoFixCapability.ASSISTED)
            ),
            "ai_suggestions": sum(1 for i in issues if i.auto_fix_capability == AutoFixCapability.AI_FIX),
            "manual_review": sum(1 for i in issues if i.auto_fix_capability == AutoFixCapability.MANUAL),
            "by_category": {
                cat.value: sum(1 for i in issues if i.category == cat)
                for cat in IssueCategory
            },
            "by_source": {
                src.value: sum(1 for i in issues if i.source == src)
                for src in IssueSource
            },
        }

    def get_readiness_level(self, score: int) -> ReadinessLevel:
        """Determine document readiness based on score and critical issue count."""
        critical_count = sum(1 for i in self._issues if i.severity == IssueSeverity.CRITICAL)
        if critical_count > 0 or score < 50:
            return ReadinessLevel.DRAFT
        elif score < 70:
            return ReadinessLevel.REVIEW_NEEDED
        elif score < 85:
            return ReadinessLevel.ALMOST_READY
        else:
            return ReadinessLevel.READY

    def generate_recommendations(self, score: int) -> list[dict[str, Any]]:
        """Generate a prioritized list of up to 5 top recommendations."""
        recs: list[dict[str, Any]] = []
        prioritized = self.prioritize()[:5]

        for i, issue in enumerate(prioritized):
            recs.append(
                {
                    "priority": i + 1,
                    "title": issue.title or issue.description[:80],
                    "category": issue.category.value,
                    "severity": issue.severity.value,
                    "auto_fixable": issue.auto_fix_capability
                    in (AutoFixCapability.SAFE, AutoFixCapability.ASSISTED),
                    "estimated_score_gain": self._estimate_score_gain(issue),
                    "rule_id": issue.rule_id,
                }
            )

        return recs

    def _estimate_score_gain(self, issue: UnifiedIssue) -> int:
        """Estimate how many score points resolving this issue would recover."""
        gains = {
            IssueSeverity.CRITICAL: 15,
            IssueSeverity.HIGH: 10,
            IssueSeverity.MEDIUM: 5,
            IssueSeverity.LOW: 2,
        }
        return gains.get(issue.severity, 0)

    # ─── Properties ───────────────────────────────────────────────────────

    @property
    def issues(self) -> list[UnifiedIssue]:
        return self._issues
