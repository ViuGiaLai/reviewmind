from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityInsight:
    """A single insight about document quality."""

    type: str  # "strength", "weakness", "opportunity", "risk"
    category: str
    title: str
    description: str
    impact: str  # "high", "medium", "low"
    action_required: bool = False
    related_issues: list[str] = field(default_factory=list)  # rule_ids


@dataclass
class DocumentQualityReport:
    """Full quality report for a document."""

    overall_score: int
    readiness_level: str
    category_scores: dict[str, int]
    category_weights: dict[str, int]
    insights: list[QualityInsight]
    recommendations: list[dict[str, Any]]
    issue_summary: dict[str, Any]
    improvement_potential: int
    next_steps: list[str]
    profile_id: str
    pack_ids: list[str]


class InsightsEngine:
    def generate_report(
        self,
        issues: list,  # list of Issue objects
        score: int,
        category_scores: dict[str, int],
        profile,
        doc_stats: dict = None,
        rule_stats: dict = None,
    ) -> DocumentQualityReport:
        insights = self._generate_insights(issues, category_scores, profile)
        recommendations = self._generate_recommendations(issues, score)
        issue_summary = self._summarize_issues(issues)
        next_steps = self._generate_next_steps(issues, score, category_scores)

        # Calculate improvement potential
        auto_fixable = [i for i in issues if getattr(i, "autofix_allowed", False)]
        improvement = min(len(auto_fixable) * 5, 30)  # rough estimate

        # Readiness level
        critical_count = sum(1 for i in issues if self._get_sev(i) in ("critical", "high"))
        if critical_count > 5 or score < 50:
            readiness = "draft"
        elif score < 70:
            readiness = "review_needed"
        elif score < 85:
            readiness = "almost_ready"
        else:
            readiness = "ready"

        return DocumentQualityReport(
            overall_score=score,
            readiness_level=readiness,
            category_scores=category_scores,
            category_weights=dict(profile.weights) if hasattr(profile, "weights") else {},
            insights=insights,
            recommendations=recommendations,
            issue_summary=issue_summary,
            improvement_potential=improvement,
            next_steps=next_steps,
            profile_id=getattr(profile, "id", "unknown"),
            pack_ids=[],
        )

    def _get_sev(self, issue) -> str:
        sev = getattr(issue, "severity", None)
        return sev.value if hasattr(sev, "value") else str(sev).lower()

    def _generate_insights(self, issues, category_scores, profile) -> list[QualityInsight]:
        insights = []

        if category_scores:
            # Strengths: categories scoring >= 80
            for cat, score in category_scores.items():
                if score >= 80:
                    insights.append(
                        QualityInsight(
                            type="strength",
                            category=cat,
                            title=f"Strong {cat.title()} Quality",
                            description=f"Your document scores well in {cat} ({score}/100).",
                            impact="low",
                        )
                    )

            # Weaknesses: categories < 60
            for cat, score in category_scores.items():
                if score < 60:
                    related = [i.rule_id for i in issues if i.category == cat][:5]
                    insights.append(
                        QualityInsight(
                            type="weakness",
                            category=cat,
                            title=f"{cat.title()} Needs Attention",
                            description=(
                                f"Your document scored {score}/100 in {cat}. "
                                "This is the main area for improvement."
                            ),
                            impact="high",
                            action_required=True,
                            related_issues=related,
                        )
                    )

        # Auto-fix opportunity
        auto_fixable = [i for i in issues if getattr(i, "autofix_allowed", False)]
        if auto_fixable:
            insights.append(
                QualityInsight(
                    type="opportunity",
                    category="general",
                    title=f"{len(auto_fixable)} Issues Can Be Auto-Fixed",
                    description=(
                        f"{len(auto_fixable)} issues can be automatically fixed, "
                        "potentially improving your score significantly."
                    ),
                    impact="high",
                    action_required=True,
                )
            )

        return insights

    def _generate_recommendations(self, issues, score) -> list[dict]:
        recs = []
        # Sort by severity and auto-fix availability
        sorted_issues = sorted(
            issues,
            key=lambda i: (
                0
                if self._get_sev(i) == "critical"
                else 1
                if self._get_sev(i) == "high"
                else 2
                if self._get_sev(i) == "medium"
                else 3
            ),
        )[:10]

        for idx, issue in enumerate(sorted_issues):
            recs.append(
                {
                    "priority": idx + 1,
                    "rule_id": getattr(issue, "rule_id", ""),
                    "category": getattr(issue, "category", ""),
                    "severity": self._get_sev(issue),
                    "message": getattr(issue, "message", ""),
                    "recommendation": getattr(issue, "recommendation", ""),
                    "auto_fixable": getattr(issue, "autofix_allowed", False),
                    "estimated_gain": {
                        "critical": 15,
                        "high": 10,
                        "medium": 5,
                        "low": 2,
                    }.get(self._get_sev(issue), 2),
                }
            )
        return recs

    def _summarize_issues(self, issues) -> dict:
        by_sev: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        by_cat: dict[str, int] = {}
        by_source: dict[str, int] = {"rule": 0, "ai": 0}

        for issue in issues:
            sev = self._get_sev(issue)
            by_sev[sev] = by_sev.get(sev, 0) + 1
            cat = getattr(issue, "category", "other")
            by_cat[cat] = by_cat.get(cat, 0) + 1
            src = getattr(issue, "source", "rule")
            by_source[src] = by_source.get(src, 0) + 1

        return {
            "total": len(issues),
            "by_severity": by_sev,
            "by_category": by_cat,
            "by_source": by_source,
            "auto_fixable": sum(1 for i in issues if getattr(i, "autofix_allowed", False)),
        }

    def _generate_next_steps(self, issues, score, category_scores) -> list[str]:
        steps = []

        critical_high = [i for i in issues if self._get_sev(i) in ("critical", "high")]
        if critical_high:
            steps.append(f"Fix {len(critical_high)} critical/high severity issues first")

        auto_fixable = [i for i in issues if getattr(i, "autofix_allowed", False)]
        if auto_fixable:
            steps.append(
                f"Apply {len(auto_fixable)} available auto-fixes to quickly improve your score"
            )

        if category_scores:
            weakest_cat = min(category_scores.items(), key=lambda x: x[1])
            if weakest_cat[1] < 70:
                steps.append(
                    f"Focus on improving {weakest_cat[0]} quality "
                    f"(current: {weakest_cat[1]}/100)"
                )

        if score >= 85:
            steps.append(
                "Your document is nearly ready. Review remaining issues and submit when satisfied."
            )

        return steps
