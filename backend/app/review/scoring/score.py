from __future__ import annotations

from collections import defaultdict

from ..models import Issue
from ..profiles import Profile


class ScoreEngine:
    deductions = {"high": 20, "medium": 10, "low": 4}

    def score(self, issues: list[Issue], profile: Profile) -> tuple[int, dict[str, int]]:
        grouped: dict[str, list[Issue]] = defaultdict(list)
        for issue in issues:
            grouped[issue.category].append(issue)
        category_scores = {
            category: max(0, 100 - sum(self.deductions[item.severity.value] for item in grouped[category]))
            for category in profile.categories
        }
        weighted_total = sum(category_scores[name] * weight for name, weight in profile.weights.items())
        weight_total = sum(profile.weights.values()) or 1
        return round(weighted_total / weight_total), category_scores
