from __future__ import annotations

import re
from collections.abc import Iterable

from ..models import DocumentModel, Evidence, Issue, Severity
from ..profiles import Profile


class RulePipeline:
    """Deterministic stages run first; an LLM stage can be registered later without changing consumers."""

    def run(self, document: DocumentModel, profile: Profile, categories: set[str]) -> list[Issue]:
        issues: list[Issue] = []
        if "structure" in categories:
            issues.extend(self._structure_rules(document, profile))
        if "writing" in categories:
            issues.extend(self._writing_rules(document, profile))
        if "citation" in categories:
            issues.extend(self._citation_rules(document))
        if "compliance" in categories:
            issues.extend(self._sop_rules(document))
        return issues

    def _structure_rules(self, document: DocumentModel, profile: Profile) -> Iterable[Issue]:
        seen = {title.casefold() for _, title, _ in document.headings}
        for section in profile.required_sections:
            if section.casefold() not in seen:
                yield Issue(
                    id=f"structure-missing-{section.casefold().replace(' ', '-')}", category="structure",
                    rule_id="structure.required-section", severity=Severity.HIGH,
                    message=f"Missing required section: {section}.",
                    recommendation=f"Add a clear '{section}' section.",
                    evidence=Evidence("No matching heading found.", 1, 1, "document"), confidence=100,
                    source="syntax-rule",
                )
        levels = [level for level, _, _ in document.headings]
        for expected, actual in zip(levels, levels[1:]):
            if actual > expected + 1:
                yield Issue(
                    id=f"structure-heading-gap-{actual}", category="structure", rule_id="structure.heading-hierarchy",
                    severity=Severity.MEDIUM, message="Heading levels skip a hierarchy level.",
                    recommendation="Use consecutive heading levels (for example, H2 then H3).",
                    evidence=Evidence("Heading hierarchy jump", 1, 1, "headings"), confidence=100,
                    source="syntax-rule", autofix_allowed=True,
                )

    def _writing_rules(self, document: DocumentModel, profile: Profile) -> Iterable[Issue]:
        for line_no, line in enumerate(document.lines, 1):
            words = re.findall(r"\b\w+\b", line)
            if len(words) > 40:
                yield Issue(
                    id=f"writing-long-sentence-{line_no}", category="writing", rule_id="writing.sentence-length",
                    severity=Severity.LOW, message="This sentence is hard to scan because it is very long.",
                    recommendation="Split it into shorter sentences while preserving the meaning.",
                    evidence=Evidence(line[:220], line_no, line_no, f"line {line_no}"), confidence=92,
                    source="semantic-rule", autofix_allowed=profile.permissions.get("writing", 0) >= 3,
                )

    def _citation_rules(self, document: DocumentModel) -> Iterable[Issue]:
        citation_count = len(re.findall(r"\[[^\]]+\]|\([A-Z][A-Za-z-]+,?\s*\d{4}\)", document.text))
        if citation_count and not document.references:
            yield Issue(
                id="citation-missing-reference-list", category="citation", rule_id="citation.reference-list",
                severity=Severity.HIGH, message="In-text citations were found but no reference list was detected.",
                recommendation="Add a References or Bibliography heading and complete entries.",
                evidence=Evidence("Citation markers detected", 1, 1, "document"), confidence=96, source="cross-rule",
            )
        if document.references and not citation_count:
            yield Issue(
                id="citation-orphan-reference-list", category="citation", rule_id="citation.in-text-match",
                severity=Severity.MEDIUM, message="A reference list was found but no in-text citation pattern was detected.",
                recommendation="Verify that every cited source is referenced in the body.",
                evidence=Evidence(document.references[0][:220], 1, 1, "references"), confidence=78, source="cross-rule",
            )

    def _sop_rules(self, document: DocumentModel) -> Iterable[Issue]:
        text = document.text.casefold()
        if "warning" not in text and "cảnh báo" not in text:
            yield Issue(
                id="compliance-safety-warning", category="compliance", rule_id="compliance.safety-warning",
                severity=Severity.HIGH, message="No safety warning was detected.",
                recommendation="Add an explicit safety warning where the procedure can create risk.",
                evidence=Evidence("No warning marker found.", 1, 1, "document"), confidence=88, source="semantic-rule",
            )
