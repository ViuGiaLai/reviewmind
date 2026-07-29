from __future__ import annotations

from typing import Any


class ContextBuilder:
    """Builds structured context for LLM prompts from document data, issues, rubric, and knowledge packs."""

    MAX_DOCUMENT_CHARS = 50000  # Truncate document to avoid token limits
    MAX_ISSUE_CHARS = 10000

    def build_review_context(
        self,
        document_text: str,
        profile_name: str = "academic",
        pack_names: list[str] | None = None,
        categories: list[str] | None = None,
        existing_issues: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build context for a full document review."""
        return {
            "document_text": self._truncate(document_text, self.MAX_DOCUMENT_CHARS),
            "profile": profile_name,
            "packs": ", ".join(pack_names or []),
            "categories": ", ".join(categories or []),
            "existing_issues": self._format_issues(existing_issues or []),
            "document_excerpt": self._truncate(document_text, 3000),
            "profile_info": profile_name,
            "pack_context": ", ".join(pack_names or []),
            "issues_summary": self._format_issues(existing_issues or []),
        }

    def build_explain_context(
        self,
        issue: dict[str, Any],
        profile_name: str = "academic",
        knowledge_pack: str = "",
    ) -> dict[str, Any]:
        """Build context for explaining a single issue."""
        return {
            "message": issue.get("message", ""),
            "category": issue.get("category", ""),
            "rule_id": issue.get("rule_id", ""),
            "severity": issue.get("severity", ""),
            "evidence": issue.get("evidence_excerpt", ""),
            "recommendation": issue.get("recommendation", ""),
            "profile": profile_name,
            "knowledge_pack": knowledge_pack,
        }

    def build_fix_context(
        self,
        text: str,
        rule_id: str,
        category: str,
        recommendation: str,
    ) -> dict[str, Any]:
        """Build context for generating an auto-fix."""
        return {
            "text": text,
            "rule_id": rule_id,
            "category": category,
            "recommendation": recommendation,
        }

    def build_summary_context(
        self,
        score: int,
        category_scores: dict[str, int],
        issue_count: int,
        top_issues: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build context for generating a review summary."""
        return {
            "score": score,
            "category_scores": self._format_category_scores(category_scores),
            "issue_count": issue_count,
            "high": sum(1 for i in top_issues if i.get("severity") == "high"),
            "medium": sum(1 for i in top_issues if i.get("severity") == "medium"),
            "low": sum(1 for i in top_issues if i.get("severity") == "low"),
            "categories": ", ".join(
                f"{cat}: {sc}" for cat, sc in sorted(category_scores.items(), key=lambda x: x[1])
            ),
            "top_issues": self._format_issues(top_issues[:5]),
        }

    def build_roadmap_context(
        self,
        score: int,
        issues: list[dict[str, Any]],
        category_scores: dict[str, int],
    ) -> dict[str, Any]:
        """Build context for generating a fix roadmap."""
        return self.build_summary_context(score, category_scores, len(issues), issues)

    def _truncate(self, text: str, max_chars: int) -> str:
        """Truncate text while preserving word boundaries."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rsplit(" ", 1)[0] + "\n\n...[truncated]..."

    def _format_issues(self, issues: list[dict[str, Any]]) -> str:
        """Format issues as a readable string."""
        if not issues:
            return "None"
        parts = []
        for i in issues[:20]:  # Limit to top 20
            parts.append(
                f"[{i.get('severity', 'low').upper()}] {i.get('rule_id', '')}: "
                f"{i.get('message', '')[:100]}"
            )
        return "\n".join(parts)

    def _format_category_scores(self, scores: dict[str, int]) -> str:
        """Format category scores."""
        return ", ".join(f"{cat}: {sc}" for cat, sc in sorted(scores.items()))


# Global instance
context_builder = ContextBuilder()
