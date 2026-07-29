from __future__ import annotations

from .models import FixConfidence, Suggestion


class FixConfidenceCalculator:
    """Calculate fix confidence based on rule type, category, and context."""

    # Rules that are 100% safe to auto-apply
    SAFE_RULES: set[str] = {
        "heading-numbering", "heading-hierarchy", "font-size", "line-spacing",
        "paragraph-spacing", "margin", "page-number", "header", "footer",
        "caption-numbering", "figure-numbering", "table-numbering",
        "table-of-contents", "list-of-figures", "list-of-tables",
        "reference-formatting", "broken-hyperlinks", "cross-reference",
    }

    # Rules that are high confidence (formatting only)
    HIGH_CONFIDENCE_RULES: set[str] = {
        "heading-style", "font-family", "bold-italic-consistency",
        "bullet-list", "numbered-list", "caption-style",
        "apa-citation", "ieee-citation", "doi-validation",
        "url-validation",
    }

    # Rules that need AI review (medium confidence)
    MEDIUM_CONFIDENCE_RULES: set[str] = {
        "passive-voice", "grammar", "spelling", "punctuation",
        "weak-wording", "hedging", "long-sentences",
        "repetition", "terminology-consistency",
    }

    # Rules that are suggestion-only (low confidence)
    SUGGESTION_RULES: set[str] = {
        "tone-consistency", "academic-tone", "business-tone",
        "sop-imperative", "readability", "clarity-improvement",
        "logic-suggestions", "writing-improvement", "ai-rewrite",
    }

    # Categories and their base confidence
    CATEGORY_CONFIDENCE: dict[str, int] = {
        "format": 98,
        "citation": 92,
        "structure": 88,
        "figure_table": 95,
        "writing": 75,
        "grammar": 80,
        "logic": 60,
        "compliance": 85,
        "ai_analysis": 50,
    }

    def calculate(self, suggestion: Suggestion) -> FixConfidence:
        """Calculate fix confidence for a suggestion."""
        reasons: list[str] = []

        # Rule-based confidence
        if suggestion.rule_id in self.SAFE_RULES:
            score = 100
            reasons.append("Deterministic rule - safe to auto-apply")
        elif suggestion.rule_id in self.HIGH_CONFIDENCE_RULES:
            score = 92
            reasons.append("High-confidence formatting rule")
        elif suggestion.rule_id in self.MEDIUM_CONFIDENCE_RULES:
            score = 72
            reasons.append("May need context review")
        elif suggestion.rule_id in self.SUGGESTION_RULES:
            score = 45
            reasons.append("AI suggestion - review recommended")
        else:
            # Fallback: use category-based confidence
            score = self.CATEGORY_CONFIDENCE.get(suggestion.category, 60)
            reasons.append(f"Based on {suggestion.category} category rules")

        # Adjust for fix type
        if suggestion.fix_type == "safe":
            score = min(100, score + 5)
        elif suggestion.fix_type == "ai":
            score = max(20, score - 10)
            reasons.append("AI-generated fix - verify before applying")

        # Adjust based on severity
        if suggestion.severity == "high":
            score = max(30, score - 5)
            reasons.append("High severity - extra caution advised")
        elif suggestion.severity == "low":
            score = min(100, score + 3)

        # Ensure score is within bounds
        score = max(5, min(100, score))

        return FixConfidence(score=score, reasons=reasons)

    def categorize_fix_type(self, suggestion: Suggestion) -> str:
        """Determine the fix type based on confidence and permissions."""
        conf = self.calculate(suggestion)

        if conf.score >= 95:
            return "safe"  # Can auto-apply
        elif conf.score >= 60:
            return "confirm"  # Needs user confirmation
        elif conf.score >= 30:
            return "review"  # Needs user review
        else:
            return "manual"  # Manual only
