from __future__ import annotations

from pathlib import Path

from .models import ReviewRequest, ReviewResult
from .parser import TextParser
from .profiles import ProfileLoader
from .report import render_markdown
from .rule_engine import RulePipeline
from .scoring import ScoreEngine


class ReviewEngine:
    def __init__(self, config_directory: Path | None = None):
        config_directory = config_directory or Path(__file__).resolve().parents[2] / "config"
        self.profiles = ProfileLoader(config_directory)
        self.parser = TextParser()
        self.rules = RulePipeline()
        self.scoring = ScoreEngine()

    def review(self, request: ReviewRequest) -> ReviewResult:
        profile = self.profiles.load(request.profile_id)
        document = self.parser.parse(request.text, request.filename, request.content_type)
        categories = set(request.enabled_categories or profile.categories) & set(profile.categories)
        issues = self.rules.run(document, profile, categories)
        score, category_scores = self.scoring.score(issues, profile)
        return ReviewResult(
            profile_id=profile.id, pack_ids=request.pack_ids, issues=issues, score=score,
            category_scores=category_scores,
            summary=f"Found {len(issues)} issue(s) across {len(categories)} enabled category/categories.",
            report_markdown=render_markdown(profile.id, score, issues),
        )
