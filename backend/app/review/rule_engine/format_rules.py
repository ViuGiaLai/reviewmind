"""Format rules: font consistency, margins, heading style, numbering, template compliance."""

from __future__ import annotations

import re
from typing import Any

from ..models import BlockType, DocumentModel, Evidence, Issue, Severity
from ..profiles import Profile
from .registry import rule

# Common academic fonts
ACADEMIC_FONTS = {"Times New Roman", "Times", "Garamond", "Palatino", "Georgia", "Cambria"}
MONO_FONTS = {"Courier New", "Consolas", "Monaco", "Fira Code", "Source Code Pro"}

# Common heading number patterns
NUMBERED_HEADING = re.compile(r"^\d+(?:\.\d+)*\s+")
ROMAN_HEADING = re.compile(r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X|MC|MR|M|C|D|L|X|V|I)+\.?\s+")


# ── Heading Consistency ───────────────────────────────────────────────────────

@rule(
    id="format.heading-numbering",
    category="format",
    name="Heading numbering consistency",
    description="Checks if all headings use consistent numbering style.",
    severity=Severity.MEDIUM,
    priority=10,
    source="syntax-rule",
)
def heading_numbering_consistency(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    numbered = 0
    unnumbered = 0
    roman = 0

    for _, title, line_no in document.headings:
        if NUMBERED_HEADING.match(title):
            numbered += 1
        elif ROMAN_HEADING.match(title):
            roman += 1
        else:
            unnumbered += 1

    total = numbered + unnumbered + roman
    if total < 2:
        return issues

    # Mixed numbering styles
    styles = sum(1 for x in [numbered > 0, unnumbered > 0, roman > 0] if x)
    if styles > 1:
        issues.append(
            Issue(
                id="format.mixed-numbering",
                category="format",
                rule_id="format.heading-numbering",
                severity=Severity.MEDIUM,
                message="Headings use mixed numbering styles (numbered, unnumbered, roman).",
                recommendation="Choose one numbering style and apply consistently across all headings.",
                evidence=Evidence(
                    f"{numbered} numbered, {unnumbered} unnumbered, {roman} roman headings",
                    1, 1, "headings",
                ),
                confidence=95,
                source="syntax-rule",
                autofix_allowed=False,
            )
        )

    return issues


@rule(
    id="format.heading-hierarchy-deep",
    category="format",
    name="Heading hierarchy check",
    description="Detects deeply nested headings or skips in heading levels.",
    severity=Severity.MEDIUM,
    priority=8,
    source="syntax-rule",
    autofix_allowed=True,
)
def heading_hierarchy_deep(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    levels = [level for level, _, _ in document.headings]

    if not levels:
        return issues

    # Check for skipped levels
    for i in range(len(levels) - 1):
        if levels[i + 1] > levels[i] + 1:
            issues.append(
                Issue(
                    id=f"format.heading-skip-{i}",
                    category="format",
                    rule_id="format.heading-hierarchy-deep",
                    severity=Severity.MEDIUM,
                    message=f"Heading level jumps from H{levels[i]} to H{levels[i + 1]}.",
                    recommendation=f"Use H{levels[i] + 1} instead of H{levels[i + 1]} for the sub-heading.",
                    evidence=Evidence(
                        f"Heading level {levels[i]} → {levels[i + 1]} at heading index {i + 2}",
                        1, 1, "headings",
                    ),
                    confidence=100,
                    source="syntax-rule",
                    autofix_allowed=True,
                )
            )

    # Check for too many levels
    max_level = max(levels)
    if max_level > 4:
        issues.append(
            Issue(
                id="format.heading-too-deep",
                category="format",
                rule_id="format.heading-hierarchy-deep",
                severity=Severity.LOW,
                message=f"Document uses up to H{max_level}, which may be too deep.",
                recommendation="Consider restructuring to keep headings within H1-H4.",
                evidence=Evidence(
                    f"Maximum heading depth: H{max_level}",
                    1, 1, "headings",
                ),
                confidence=80,
                source="syntax-rule",
            )
        )

    # First heading should be H1
    if levels and levels[0] != 1:
        issues.append(
            Issue(
                id="format.first-heading-not-h1",
                category="format",
                rule_id="format.heading-hierarchy-deep",
                severity=Severity.LOW,
                message="The first heading is not H1.",
                recommendation="Start with an H1 heading for the main title.",
                evidence=Evidence(
                    f"First heading is H{levels[0]}",
                    1, 1, "headings",
                ),
                confidence=95,
                source="syntax-rule",
                autofix_allowed=True,
            )
        )

    return issues


# ── Template Compliance ────────────────────────────────────────────────────────

@rule(
    id="format.required-sections-depth",
    category="format",
    name="Required sections check",
    description="Verifies that all required sections exist at proper heading levels.",
    severity=Severity.HIGH,
    priority=15,
    source="syntax-rule",
)
def required_sections_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if not profile.required_sections:
        return issues

    seen_headings = {title.casefold(): level for level, title, _ in document.headings}

    for section in profile.required_sections:
        section_lower = section.casefold()
        if section_lower not in seen_headings:
            issues.append(
                Issue(
                    id=f"format.missing-section-{section_lower.replace(' ', '-')}",
                    category="format",
                    rule_id="format.required-sections-depth",
                    severity=Severity.HIGH,
                    message=f"Missing required section: '{section}'.",
                    recommendation=f"Add a clear '{section}' section heading (H1 or H2).",
                    evidence=Evidence(
                        f"Required section '{section}' not found in headings",
                        1, 1, "headings",
                    ),
                    confidence=100,
                    source="syntax-rule",
                )
            )

    return issues


# ── Section Length ─────────────────────────────────────────────────────────────

@rule(
    id="format.section-length",
    category="format",
    name="Unusual section length",
    description="Flags sections that are unusually short or long.",
    severity=Severity.LOW,
    priority=5,
    source="semantic-rule",
)
def section_length_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    min_words = config.get("min_words", 20)
    max_words = config.get("max_words", 2000)

    # Track words between headings
    heading_positions: list[tuple[int, str, int]] = [
        (level, title, line_no)
        for level, title, line_no in document.headings
    ]

    if len(heading_positions) < 2:
        return issues

    for i, (level, title, start_line) in enumerate(heading_positions):
        # Determine section end
        if i + 1 < len(heading_positions):
            end_line = heading_positions[i + 1][2] - 1
        else:
            end_line = len(document.lines)

        # Count words in section
        section_lines = document.lines[start_line:end_line]
        section_text = " ".join(section_lines)
        word_count = len(section_text.split())

        if word_count < min_words:
            issues.append(
                Issue(
                    id=f"format.short-section-{i}",
                    category="format",
                    rule_id="format.section-length",
                    severity=Severity.LOW,
                    message=f"Section '{title}' is very short ({word_count} words).",
                    recommendation=f"Consider expanding the section or merging it with another section.",
                    evidence=Evidence(
                        f"'{title}' has {word_count} words (min: {min_words})",
                        start_line, end_line, f"line {start_line}",
                    ),
                    confidence=85,
                    source="semantic-rule",
                )
            )
        elif word_count > max_words:
            issues.append(
                Issue(
                    id=f"format.long-section-{i}",
                    category="format",
                    rule_id="format.section-length",
                    severity=Severity.LOW,
                    message=f"Section '{title}' is very long ({word_count} words).",
                    recommendation="Consider splitting into sub-sections.",
                    evidence=Evidence(
                        f"'{title}' has {word_count} words (max: {max_words})",
                        start_line, end_line, f"line {start_line}",
                    ),
                    confidence=80,
                    source="semantic-rule",
                )
            )

    return issues


# ── Block-level Format Checks ──────────────────────────────────────────────────

@rule(
    id="format.block-format",
    category="format",
    name="Block formatting inconsistencies",
    description="Checks for formatting issues in document blocks if rich structure is available.",
    severity=Severity.LOW,
    priority=3,
    source="syntax-rule",
)
def block_format_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if not document.blocks:
        return issues  # No rich structure available

    # Check heading font consistency
    heading_fonts: set[str] = set()
    for block in document.blocks:
        if block.type == BlockType.HEADING and block.font_name:
            heading_fonts.add(block.font_name.lower())

    if len(heading_fonts) > 1:
        issues.append(
            Issue(
                id="format.heading-font-mismatch",
                category="format",
                rule_id="format.block-format",
                severity=Severity.LOW,
                message="Headings use different fonts.",
                recommendation="Use the same font for all headings.",
                evidence=Evidence(
                    f"Found fonts: {', '.join(heading_fonts)}",
                    1, 1, "blocks",
                ),
                confidence=90,
                source="syntax-rule",
            )
        )

    # Check for mixed alignments in consecutive paragraphs
    alignments: list[str] = []
    for block in document.blocks:
        if block.type in (BlockType.PARAGRAPH, BlockType.HEADING):
            alignments.append(block.alignment)

    if len(alignments) >= 3:
        unique_alignments = set(alignments[:10])
        if len(unique_alignments) > 2:
            issues.append(
                Issue(
                    id="format.mixed-alignment",
                    category="format",
                    rule_id="format.block-format",
                    severity=Severity.LOW,
                    message="Document uses multiple text alignments inconsistently.",
                    recommendation=f"Stick to one alignment (usually 'justify' or 'left').",
                    evidence=Evidence(
                        f"Alignments found: {', '.join(unique_alignments)}",
                        1, 1, "blocks",
                    ),
                    confidence=75,
                    source="semantic-rule",
                )
            )

    return issues
