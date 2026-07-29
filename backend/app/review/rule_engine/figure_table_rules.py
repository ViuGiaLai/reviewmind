"""Figure & Table rules: numbering, captions, cross-references, missing figures/tables, equations."""

from __future__ import annotations

import re
from typing import Any

from ..models import BlockType, DocumentModel, Evidence, Issue, Severity
from ..profiles import Profile
from .registry import rule

# ── Patterns ──────────────────────────────────────────────────────────────────

FIGURE_REF = re.compile(r"(?:Fig(?:ure)?\.?\s*)(\d+(?:\.\d+)*)", re.I)
TABLE_REF = re.compile(r"(?:Tabl(?:e)?\.?\s*)(\d+(?:\.\d+)*)", re.I)
EQUATION_REF = re.compile(r"(?:Eq(?:uation)?\.?\s*)(\d+(?:\.\d+)*)", re.I)

CAPTION_PATTERN = re.compile(
    r"(?:Figure|Fig\.?|Table|Tabl\.?|Equation|Eq\.?)\s*(\d+(?:\.\d+)*)[.:]\s*(.+)",
    re.I,
)

# Common alt-text for missing figures
PLACEHOLDER_PATTERNS = [
    re.compile(r"insert\s+(figure|image|picture|graph|chart)", re.I),
    re.compile(r"figure\s+\d+\s+(here|about|above|below)", re.I),
    re.compile(r"\[?\s*image\s*(not\s+)?(found|missing|unavailable)\s*\]?", re.I),
    re.compile(r"todo:\s*add\s+(figure|image)", re.I),
]


# ── Figure Numbering ──────────────────────────────────────────────────────────

@rule(
    id="figure.numbering-sequential",
    category="figure_table",
    name="Figure numbering check",
    description="Checks that figures are numbered sequentially and consistently.",
    severity=Severity.MEDIUM,
    priority=30,
    source="syntax-rule",
)
def figure_numbering_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []

    # Extract figure numbers from captions and references
    figure_numbers: list[int] = []
    for block in document.blocks:
        if block.type == BlockType.FIGURE:
            if block.figure and block.figure.caption:
                m = re.search(r"(\d+)", block.figure.caption)
                if m:
                    figure_numbers.append(int(m.group(1)))
        elif block.type == BlockType.CAPTION and block.text:
            if re.search(r"(figure|fig\.?)", block.text, re.I):
                m = re.search(r"(\d+)", block.text)
                if m:
                    figure_numbers.append(int(m.group(1)))

    # If no rich blocks, check text patterns
    if not figure_numbers:
        for line_no, line in enumerate(document.lines, 1):
            m = CAPTION_PATTERN.search(line)
            if m and re.search(r"(figure|fig\.?)", m.group(0), re.I):
                try:
                    figure_numbers.append(int(m.group(1)))
                except ValueError:
                    pass

    if len(figure_numbers) >= 2:
        # Check sequential
        expected = figure_numbers[0]
        for i, actual in enumerate(figure_numbers):
            if actual != expected:
                issues.append(
                    Issue(
                        id=f"figure.numbering-gap-{actual}",
                        category="figure_table",
                        rule_id="figure.numbering-sequential",
                        severity=Severity.MEDIUM,
                        message=f"Figure numbering gap or skip: found Figure {actual}, expected Figure {expected}.",
                        recommendation="Renumber figures sequentially (Figure 1, 2, 3...).",
                        evidence=Evidence(
                            f"Expected Figure {expected}, found Figure {actual}",
                            1, 1, "document",
                        ),
                        confidence=85,
                        source="syntax-rule",
                    )
                )
                break
            expected += 1

    return issues


# ── Table Numbering ───────────────────────────────────────────────────────────

@rule(
    id="figure.table-numbering",
    category="figure_table",
    name="Table numbering check",
    description="Checks that tables are numbered sequentially.",
    severity=Severity.MEDIUM,
    priority=30,
    source="syntax-rule",
)
def table_numbering_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []

    table_numbers: list[int] = []
    for block in document.blocks:
        if block.type == BlockType.TABLE:
            if block.table and block.table.caption:
                m = re.search(r"(\d+)", block.table.caption)
                if m:
                    table_numbers.append(int(m.group(1)))
        elif block.type == BlockType.CAPTION and block.text:
            if re.search(r"tabl(e|\.)", block.text, re.I):
                m = re.search(r"(\d+)", block.text)
                if m:
                    table_numbers.append(int(m.group(1)))

    if not table_numbers:
        for line_no, line in enumerate(document.lines, 1):
            m = CAPTION_PATTERN.search(line)
            if m and re.search(r"tabl(e|\.)", m.group(0), re.I):
                try:
                    table_numbers.append(int(m.group(1)))
                except ValueError:
                    pass

    if len(table_numbers) >= 2:
        expected = table_numbers[0]
        for actual in table_numbers:
            if actual != expected:
                issues.append(
                    Issue(
                        id=f"figure.table-gap-{actual}",
                        category="figure_table",
                        rule_id="figure.table-numbering",
                        severity=Severity.MEDIUM,
                        message=f"Table numbering gap: found Table {actual}, expected Table {expected}.",
                        recommendation="Renumber tables sequentially (Table 1, 2, 3...).",
                        evidence=Evidence(
                            f"Expected Table {expected}, found Table {actual}",
                            1, 1, "document",
                        ),
                        confidence=85,
                        source="syntax-rule",
                    )
                )
                break
            expected += 1

    return issues


# ── Missing Figure Caption ────────────────────────────────────────────────────

@rule(
    id="figure.missing-caption",
    category="figure_table",
    name="Missing figure caption",
    description="Detects figures without captions.",
    severity=Severity.HIGH,
    priority=35,
    source="syntax-rule",
)
def missing_figure_caption(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []

    for block in document.blocks:
        if block.type == BlockType.FIGURE:
            has_caption = block.figure and bool(block.figure.caption)
            if not has_caption:
                issues.append(
                    Issue(
                        id=f"figure.missing-caption-{block.node_id[:8]}",
                        category="figure_table",
                        rule_id="figure.missing-caption",
                        severity=Severity.HIGH,
                        message="Figure is missing a caption.",
                        recommendation="Add a caption to the figure (e.g., 'Figure 1: Description').",
                        evidence=Evidence(
                            "Figure without caption",
                            block.location.line_start,
                            block.location.line_end,
                            block.location.location or f"block {block.node_id[:8]}",
                        ),
                        confidence=100,
                        source="syntax-rule",
                    )
                )

    # Text-based detection
    for line_no, line in enumerate(document.lines, 1):
        # Detect image references without captions
        has_image = bool(re.search(r"!\[.*?\]\(.*?\)", line))
        if has_image:
            next_line = document.lines[line_no] if line_no < len(document.lines) else ""
            if next_line and not re.search(r"figure|fig\.", next_line, re.I):
                # Check for placeholder patterns
                if any(p.search(line) for p in PLACEHOLDER_PATTERNS):
                    issues.append(
                        Issue(
                            id=f"figure.placeholder-{line_no}",
                            category="figure_table",
                            rule_id="figure.missing-caption",
                            severity=Severity.MEDIUM,
                            message="Figure placeholder detected without actual content.",
                            recommendation="Replace with the actual figure and add a caption.",
                            evidence=Evidence(
                                line[:200], line_no, line_no, f"line {line_no}",
                            ),
                            confidence=90,
                            source="semantic-rule",
                        )
                    )

    return issues


# ── Missing Table Caption ─────────────────────────────────────────────────────

@rule(
    id="figure.missing-table-caption",
    category="figure_table",
    name="Missing table caption",
    description="Detects tables without captions.",
    severity=Severity.HIGH,
    priority=35,
    source="syntax-rule",
)
def missing_table_caption(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []

    for block in document.blocks:
        if block.type == BlockType.TABLE:
            has_caption = block.table and bool(block.table.caption)
            if not has_caption:
                issues.append(
                    Issue(
                        id=f"figure.missing-table-caption-{block.node_id[:8]}",
                        category="figure_table",
                        rule_id="figure.missing-table-caption",
                        severity=Severity.HIGH,
                        message="Table is missing a caption.",
                        recommendation="Add a caption to the table (e.g., 'Table 1: Description').",
                        evidence=Evidence(
                            "Table without caption",
                            block.location.line_start,
                            block.location.line_end,
                            block.location.location or f"block {block.node_id[:8]}",
                        ),
                        confidence=100,
                        source="syntax-rule",
                    )
                )

    return issues


# ── Cross-Reference Mismatch ──────────────────────────────────────────────────

@rule(
    id="figure.cross-reference",
    category="figure_table",
    name="Cross-reference mismatches",
    description="Checks that cross-references to figures/tables point to existing items.",
    severity=Severity.MEDIUM,
    priority=25,
    source="cross-rule",
)
def cross_reference_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []

    # Collect actual figure numbers
    actual_figures: set[int] = set()
    actual_tables: set[int] = set()
    actual_equations: set[int] = set()

    for block in document.blocks:
        if block.figure and block.figure.caption:
            m = re.search(r"(\d+)", block.figure.caption)
            if m:
                actual_figures.add(int(m.group(1)))
        if block.table and block.table.caption:
            m = re.search(r"(\d+)", block.table.caption)
            if m:
                actual_tables.add(int(m.group(1)))

    # Also check caption blocks
    for line_no, line in enumerate(document.lines, 1):
        m = CAPTION_PATTERN.search(line)
        if m:
            try:
                num = int(m.group(1))
                prefix = m.group(0).lower()
                if "figure" in prefix or "fig" in prefix:
                    actual_figures.add(num)
                elif "table" in prefix:
                    actual_tables.add(num)
            except ValueError:
                pass

    # Check cross-references
    for line_no, line in enumerate(document.lines, 1):
        # Figure references
        for m in FIGURE_REF.finditer(line):
            try:
                ref_num = int(m.group(1))
                if actual_figures and ref_num not in actual_figures:
                    issues.append(
                        Issue(
                            id=f"figure.ref-mismatch-{ref_num}",
                            category="figure_table",
                            rule_id="figure.cross-reference",
                            severity=Severity.MEDIUM,
                            message=f"Cross-reference to Figure {ref_num} but no such figure exists.",
                            recommendation=f"Verify the figure number or add Figure {ref_num}.",
                            evidence=Evidence(
                                line[:200], line_no, line_no, f"line {line_no}",
                            ),
                            confidence=85,
                            source="cross-rule",
                        )
                    )
            except ValueError:
                pass

        # Table references
        for m in TABLE_REF.finditer(line):
            try:
                ref_num = int(m.group(1))
                if actual_tables and ref_num not in actual_tables:
                    issues.append(
                        Issue(
                            id=f"figure.table-ref-mismatch-{ref_num}",
                            category="figure_table",
                            rule_id="figure.cross-reference",
                            severity=Severity.MEDIUM,
                            message=f"Cross-reference to Table {ref_num} but no such table exists.",
                            recommendation=f"Verify the table number or add Table {ref_num}.",
                            evidence=Evidence(
                                line[:200], line_no, line_no, f"line {line_no}",
                            ),
                            confidence=85,
                            source="cross-rule",
                        )
                    )
            except ValueError:
                pass

        # Equation references
        for m in EQUATION_REF.finditer(line):
            try:
                ref_num = int(m.group(1))
                if actual_equations and ref_num not in actual_equations:
                    issues.append(
                        Issue(
                            id=f"figure.eq-ref-mismatch-{ref_num}",
                            category="figure_table",
                            rule_id="figure.cross-reference",
                            severity=Severity.LOW,
                            message=f"Cross-reference to Equation {ref_num} but no such equation exists.",
                            recommendation=f"Verify the equation number.",
                            evidence=Evidence(
                                line[:200], line_no, line_no, f"line {line_no}",
                            ),
                            confidence=75,
                            source="cross-rule",
                        )
                    )
            except ValueError:
                pass

    # Check for figures/tables that exist but aren't referenced
    if actual_figures:
        refd_figures: set[int] = set()
        for line_no, line in enumerate(document.lines, 1):
            for m in FIGURE_REF.finditer(line):
                try:
                    refd_figures.add(int(m.group(1)))
                except ValueError:
                    pass
        for fig_num in actual_figures:
            if fig_num not in refd_figures:
                issues.append(
                    Issue(
                        id=f"figure.not-referenced-{fig_num}",
                        category="figure_table",
                        rule_id="figure.cross-reference",
                        severity=Severity.LOW,
                        message=f"Figure {fig_num} exists but is not referenced in the text.",
                        recommendation=f"Add a cross-reference to Figure {fig_num} in the body text.",
                        evidence=Evidence(
                            f"Figure {fig_num} not referenced in text",
                            1, 1, "document",
                        ),
                        confidence=90,
                        source="cross-rule",
                    )
                )

    return issues


# ── Caption Format ────────────────────────────────────────────────────────────

@rule(
    id="figure.caption-format",
    category="figure_table",
    name="Caption format check",
    description="Verifies captions follow standard formatting conventions.",
    severity=Severity.LOW,
    priority=20,
    source="syntax-rule",
)
def caption_format_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []

    for line_no, line in enumerate(document.lines, 1):
        m = CAPTION_PATTERN.search(line)
        if m:
            full_prefix = m.group(0)
            caption_text = m.group(2).strip()

            # Check for empty caption text
            if not caption_text:
                issues.append(
                    Issue(
                        id=f"figure.caption-empty-{line_no}",
                        category="figure_table",
                        rule_id="figure.caption-format",
                        severity=Severity.MEDIUM,
                        message=f"{full_prefix} has no descriptive text.",
                        recommendation="Add a descriptive caption after the number.",
                        evidence=Evidence(
                            line[:200], line_no, line_no, f"line {line_no}",
                        ),
                        confidence=100,
                        source="syntax-rule",
                    )
                )
                continue

            # Check for trailing period (good practice)
            if profile.id == "academic" and not caption_text.endswith("."):
                issues.append(
                    Issue(
                        id=f"figure.caption-period-{line_no}",
                        category="figure_table",
                        rule_id="figure.caption-format",
                        severity=Severity.LOW,
                        message=f"{full_prefix} caption should end with a period.",
                        recommendation="End captions with a period.",
                        evidence=Evidence(
                            caption_text[:200], line_no, line_no, f"line {line_no}",
                        ),
                        confidence=75,
                        source="syntax-rule",
                        autofix_allowed=True,
                    )
                )

            # Caption should not be too long
            if len(caption_text) > 300:
                issues.append(
                    Issue(
                        id=f"figure.caption-long-{line_no}",
                        category="figure_table",
                        rule_id="figure.caption-format",
                        severity=Severity.LOW,
                        message=f"Caption is too long ({len(caption_text)} chars).",
                        recommendation="Keep captions concise (under 300 characters).",
                        evidence=Evidence(
                            caption_text[:200], line_no, line_no, f"line {line_no}",
                        ),
                        confidence=80,
                        source="semantic-rule",
                    )
                )

    return issues


# ── Figure Used But Missing ───────────────────────────────────────────────────

@rule(
    id="figure.cited-missing",
    category="figure_table",
    name="Figure cited but missing",
    description="Detects references to figures that don't exist in the document.",
    severity=Severity.HIGH,
    priority=30,
    source="cross-rule",
)
def figure_cited_missing(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    text_lower = document.text.lower()

    # Check for "as shown in Figure X" patterns without actual figure presence
    refs = list(FIGURE_REF.finditer(document.text))
    has_figures = bool(document.figures) or bool(
        re.search(r"(?m)^(figure|fig\.)\s+\d", text_lower)
    )

    if refs and not has_figures:
        issues.append(
            Issue(
                id="figure.cited-missing-all",
                category="figure_table",
                rule_id="figure.cited-missing",
                severity=Severity.HIGH,
                message=f"{len(refs)} figure reference(s) found but no actual figures in the document.",
                recommendation="Add the referenced figures or remove the references.",
                evidence=Evidence(
                    f"{len(refs)} figure references detected without figures",
                    1, 1, "document",
                ),
                confidence=95,
                source="cross-rule",
            )
        )
        return issues

    return issues


# ── Table Cited But Missing ───────────────────────────────────────────────────

@rule(
    id="figure.table-cited-missing",
    category="figure_table",
    name="Table cited but missing",
    description="Detects references to tables that don't exist.",
    severity=Severity.HIGH,
    priority=30,
    source="cross-rule",
)
def table_cited_missing(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    refs = list(TABLE_REF.finditer(document.text))
    has_tables = bool(document.tables) or bool(
        re.search(r"(?m)^(table)\s+\d", document.text.lower())
    )

    if refs and not has_tables:
        issues.append(
            Issue(
                id="figure.table-cited-missing-all",
                category="figure_table",
                rule_id="figure.table-cited-missing",
                severity=Severity.HIGH,
                message=f"{len(refs)} table reference(s) found but no actual tables in the document.",
                recommendation="Add the referenced tables or remove the references.",
                evidence=Evidence(
                    f"{len(refs)} table references without tables",
                    1, 1, "document",
                ),
                confidence=95,
                source="cross-rule",
            )
        )

    return issues


# ── Equation Numbering ────────────────────────────────────────────────────────

@rule(
    id="figure.equation-numbering",
    category="figure_table",
    name="Equation numbering check",
    description="Checks for consistent equation numbering.",
    severity=Severity.LOW,
    priority=15,
    source="syntax-rule",
)
def equation_numbering_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if not document.equations and not document.blocks:
        return issues

    eq_count = len(document.equations)
    if eq_count > 0:
        # Check if any equations have numbering
        numbered_count = 0
        for eq in document.equations:
            if re.search(r"\(\d+\)", eq.latex) or re.search(r"\(\d+\)", eq.plain_text):
                numbered_count += 1

        if eq_count >= 3 and numbered_count == 0:
            issues.append(
                Issue(
                    id="figure.equations-not-numbered",
                    category="figure_table",
                    rule_id="figure.equation-numbering",
                    severity=Severity.LOW,
                    message=f"{eq_count} equation(s) found but none are numbered.",
                    recommendation="Number equations sequentially (1), (2), (3)... for easy cross-referencing.",
                    evidence=Evidence(
                        f"{eq_count} unnumbered equations",
                        1, 1, "document",
                    ),
                    confidence=75,
                    source="semantic-rule",
                )
            )

    return issues
