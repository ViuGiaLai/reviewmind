"""Legacy rules migrated from the original pipeline.py, registered via the decorator."""

from __future__ import annotations

import re
from typing import Any

from ..models import DocumentModel, Evidence, Issue, Severity
from ..profiles import Profile
from .registry import rule


@rule(
    id="writing.sentence-length",
    category="writing",
    name="Long sentence detection (legacy)",
    description="Flags sentences with more than 40 words.",
    severity=Severity.LOW,
    priority=22,
    source="semantic-rule",
)
def legacy_long_sentence(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    for line_no, line in enumerate(document.lines, 1):
        words = re.findall(r"\b\w+\b", line)
        if len(words) > 40:
            issues.append(
                Issue(
                    id=f"writing-long-sentence-{line_no}",
                    category="writing",
                    rule_id="writing.sentence-length",
                    severity=Severity.LOW,
                    message="This sentence is hard to scan because it is very long.",
                    recommendation="Split it into shorter sentences while preserving the meaning.",
                    evidence=Evidence(line[:220], line_no, line_no, f"line {line_no}"),
                    confidence=92,
                    source="semantic-rule",
                    autofix_allowed=profile.permissions.get("writing", 0) >= 3,
                )
            )
    return issues


@rule(
    id="structure.required-section",
    category="structure",
    name="Required section check (legacy)",
    description="Checks that all required sections exist as headings.",
    severity=Severity.HIGH,
    priority=15,
    source="syntax-rule",
)
def legacy_required_section(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    seen = {title.casefold() for _, title, _ in document.headings}
    for section in profile.required_sections:
        if section.casefold() not in seen:
            issues.append(
                Issue(
                    id=f"structure-missing-{section.casefold().replace(' ', '-')}",
                    category="structure",
                    rule_id="structure.required-section",
                    severity=Severity.HIGH,
                    message=f"Missing required section: {section}.",
                    recommendation=f"Add a clear '{section}' section.",
                    evidence=Evidence("No matching heading found.", 1, 1, "document"),
                    confidence=100,
                    source="syntax-rule",
                )
            )
    return issues


@rule(
    id="structure.heading-hierarchy",
    category="structure",
    name="Heading hierarchy (legacy)",
    description="Checks that heading levels don't skip levels.",
    severity=Severity.MEDIUM,
    priority=12,
    source="syntax-rule",
    autofix_allowed=True,
)
def legacy_heading_hierarchy(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    levels = [level for level, _, _ in document.headings]
    for expected, actual in zip(levels, levels[1:]):
        if actual > expected + 1:
            issues.append(
                Issue(
                    id=f"structure-heading-gap-{actual}",
                    category="structure",
                    rule_id="structure.heading-hierarchy",
                    severity=Severity.MEDIUM,
                    message="Heading levels skip a hierarchy level.",
                    recommendation="Use consecutive heading levels (for example, H2 then H3).",
                    evidence=Evidence("Heading hierarchy jump", 1, 1, "headings"),
                    confidence=100,
                    source="syntax-rule",
                    autofix_allowed=True,
                )
            )
    return issues


@rule(
    id="citation.reference-list",
    category="citation",
    name="Citation-reference matching (legacy)",
    description="Checks for citations without a reference list and vice versa.",
    severity=Severity.HIGH,
    priority=30,
    source="cross-rule",
)
def legacy_citation_reference(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    citation_count = len(re.findall(r"\[[^\]]+\]|\([A-Z][A-Za-z-]+,?\s*\d{4}\)", document.text))
    if citation_count and not document.references:
        issues.append(
            Issue(
                id="citation-missing-reference-list",
                category="citation",
                rule_id="citation.reference-list",
                severity=Severity.HIGH,
                message="In-text citations were found but no reference list was detected.",
                recommendation="Add a References or Bibliography heading and complete entries.",
                evidence=Evidence("Citation markers detected", 1, 1, "document"),
                confidence=96,
                source="cross-rule",
            )
        )
    if document.references and not citation_count:
        issues.append(
            Issue(
                id="citation-orphan-reference-list",
                category="citation",
                rule_id="citation.in-text-match",
                severity=Severity.MEDIUM,
                message="A reference list was found but no in-text citation pattern was detected.",
                recommendation="Verify that every cited source is referenced in the body.",
                evidence=Evidence(document.references[0][:220], 1, 1, "references"),
                confidence=78,
                source="cross-rule",
            )
        )
    return issues


@rule(
    id="compliance.safety-warning",
    category="compliance",
    name="Safety warning check (legacy)",
    description="Checks for safety warnings in SOP documents.",
    severity=Severity.HIGH,
    priority=20,
    source="semantic-rule",
)
def legacy_safety_warning(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    text = document.text.casefold()
    if "warning" not in text and "cảnh báo" not in text:
        issues.append(
            Issue(
                id="compliance-safety-warning",
                category="compliance",
                rule_id="compliance.safety-warning",
                severity=Severity.HIGH,
                message="No safety warning was detected.",
                recommendation="Add an explicit safety warning where the procedure can create risk.",
                evidence=Evidence("No warning marker found.", 1, 1, "document"),
                confidence=88,
                source="semantic-rule",
            )
        )
    return issues
