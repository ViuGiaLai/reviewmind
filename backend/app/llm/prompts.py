from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class PromptTemplate:
    """A versioned prompt template."""
    id: str
    name: str
    version: str = "1.0.0"
    system_prompt: str = ""
    user_prompt_template: str = ""
    description: str = ""
    category: str = "general"  # review, explanation, fix, summary
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def render(self, **kwargs: Any) -> str:
        """Render the user prompt template with the given variables."""
        return self.user_prompt_template.format(**kwargs)

    def render_system(self, **kwargs: Any) -> str:
        """Render the system prompt with the given variables."""
        return self.system_prompt.format(**kwargs) if self.system_prompt else ""


class PromptRegistry:
    """Registry of versioned prompt templates."""

    def __init__(self):
        self._templates: dict[str, PromptTemplate] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register built-in prompt templates."""
        defaults = [
            # ── Document Review ────────────────────────────────────────────
            PromptTemplate(
                id="review.full",
                name="Full Document Review",
                version="2.0.0",
                category="review",
                system_prompt=(
                    "You are an expert document reviewer specializing in {profile} writing standards. "
                    "Review the document for quality, structure, citations, grammar, and consistency. "
                    "Be specific, cite evidence, and provide actionable recommendations."
                ),
                user_prompt_template=(
                    "Please review the following document using {profile} standards.\n\n"
                    "Knowledge Packs: {packs}\n"
                    "Categories to check: {categories}\n\n"
                    "--- DOCUMENT ---\n{document_text}\n\n"
                    "--- EXISTING ISSUES ---\n{existing_issues}\n\n"
                    "Provide your analysis as a JSON array of issue objects. Each issue must have: category, rule_id, severity, message, recommendation, evidence_excerpt, confidence."
                ),
            ),
            PromptTemplate(
                id="review.writing",
                name="Writing Quality Review",
                version="1.1.0",
                category="review",
                system_prompt=(
                    "You are a writing quality expert. Analyze the document for:\n"
                    "1. Grammar and spelling errors\n"
                    "2. Passive voice and hedging\n"
                    "3. Sentence length and readability\n"
                    "4. Tone consistency\n"
                    "5. Terminology consistency\n"
                    "Provide specific examples for each issue found."
                ),
                user_prompt_template="Analyze this text for writing quality issues:\n\n{text}",
            ),
            # ── Issue Explanation ──────────────────────────────────────────
            PromptTemplate(
                id="explain.issue",
                name="Issue Explanation",
                version="1.0.0",
                category="explanation",
                system_prompt="You are an expert document reviewer. Explain why the following issue matters, what rule it violates, and how to fix it. Be educational.",
                user_prompt_template=(
                    "Issue: {message}\n"
                    "Category: {category}\n"
                    "Rule: {rule_id}\n"
                    "Severity: {severity}\n"
                    "Evidence: {evidence}\n"
                    "Recommendation: {recommendation}\n\n"
                    "Explain this issue in simple terms and why it matters for {profile} documents."
                ),
            ),
            # ── Auto Fix Suggestion ────────────────────────────────────────
            PromptTemplate(
                id="fix.suggest",
                name="Auto Fix Suggestion",
                version="1.0.0",
                category="fix",
                system_prompt="You are an expert editor. Suggest minimal, precise fixes. Only change what's necessary. Output JSON with 'original' and 'fixed' text.",
                user_prompt_template=(
                    "Fix the following {category} issue:\n"
                    "Rule: {rule_id}\n"
                    "Original text: \"{text}\"\n"
                    "Suggestion: {recommendation}\n\n"
                    "Provide the corrected version."
                ),
            ),
            # ── Summary ────────────────────────────────────────────────────
            PromptTemplate(
                id="summary.review",
                name="Review Summary",
                version="1.0.0",
                category="summary",
                system_prompt="You are an expert document analyst. Summarize the review results clearly and provide actionable next steps.",
                user_prompt_template=(
                    "Summarize this review:\n"
                    "Score: {score}/100\n"
                    "Category Scores: {category_scores}\n"
                    "Issues Found: {issue_count}\n"
                    "Top Issues: {top_issues}\n\n"
                    "Provide: 1) Brief summary 2) Key strengths 3) Areas to improve 4) Suggested roadmap"
                ),
            ),
            # ── Fix Roadmap ────────────────────────────────────────────────
            PromptTemplate(
                id="roadmap.fix",
                name="Fix Roadmap",
                version="1.0.0",
                category="summary",
                system_prompt="You are a document improvement coach. Create a step-by-step roadmap to fix all issues, prioritizing by impact and effort.",
                user_prompt_template=(
                    "Create a fix roadmap for this review:\n"
                    "Score: {score}/100\n"
                    "Issues: {issue_count} ({high} high, {medium} medium, {low} low)\n"
                    "Categories: {categories}\n\n"
                    "Rank fixes by: 1) Impact on score 2) Effort required 3) Dependencies between fixes"
                ),
            ),
        ]
        for template in defaults:
            self._templates[template.id] = template

    def get(self, template_id: str) -> PromptTemplate | None:
        """Get a prompt template by ID."""
        return self._templates.get(template_id)

    def register(self, template: PromptTemplate) -> None:
        """Register a new template or update existing."""
        self._templates[template.id] = template

    def list_by_category(self, category: str) -> list[PromptTemplate]:
        """List all templates in a category."""
        return [t for t in self._templates.values() if t.category == category]

    def list_all(self) -> list[PromptTemplate]:
        """List all registered templates."""
        return list(self._templates.values())

    def get_version(self, template_id: str) -> str | None:
        """Get the current version of a template."""
        template = self.get(template_id)
        return template.version if template else None

    def render(self, template_id: str, **kwargs: Any) -> tuple[str, str]:
        """Render both system and user prompts for a template."""
        template = self.get(template_id)
        if not template:
            raise ValueError(f"Unknown template: {template_id}")
        return template.render_system(**kwargs), template.render(**kwargs)


# Global registry instance
prompt_registry = PromptRegistry()
