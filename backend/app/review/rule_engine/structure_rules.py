"""Structure rules: section validation, order, completeness, empty sections, heading hierarchy."""

from __future__ import annotations

import re
from typing import Any

from ..models import DocumentModel, Evidence, Issue, Severity
from ..profiles import Profile
from .registry import rule

# Academic section patterns
ACADEMIC_SECTIONS = [
    "abstract", "keywords", "introduction", "literature review", "related work",
    "methodology", "method", "approach", "framework",
    "results", "experiment", "evaluation", "findings",
    "discussion", "conclusion", "references", "bibliography",
    "appendix", "acknowledgment", "acknowledgement",
    "supplementary material", "data availability", "conflict of interest",
]

BUSINESS_SECTIONS = [
    "executive summary", "introduction", "background",
    "problem statement", "proposed solution", "approach",
    "implementation plan", "timeline", "budget",
    "resources", "risk assessment", "expected outcomes",
    "conclusion", "recommendation", "next steps", "appendix",
]

SOP_SECTIONS = [
    "purpose", "scope", "definitions", "responsibilities",
    "procedure", "safety", "warnings", "cautions",
    "documentation", "references", "revision history", "approval",
    "attachments", "appendices",
]


def _get_profile_sections(profile_id: str) -> list[str]:
    if profile_id == "academic":
        return ACADEMIC_SECTIONS
    elif profile_id == "business":
        return BUSINESS_SECTIONS
    elif profile_id == "sop":
        return SOP_SECTIONS
    elif profile_id == "technical_design":
        return ["overview", "architecture", "components", "configuration"]
    return ACADEMIC_SECTIONS


# ── Title Check ───────────────────────────────────────────────────────────────

@rule(
    id="structure.title-check",
    category="structure",
    name="Title check",
    description="Checks if document has a proper title.",
    severity=Severity.MEDIUM,
    priority=50,
    source="syntax-rule",
)
def title_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if not document.headings:
        issues.append(
            Issue(
                id="structure.no-title",
                category="structure",
                rule_id="structure.title-check",
                severity=Severity.HIGH,
                message="Document has no title or headings.",
                recommendation="Add a title as an H1 heading at the beginning of the document.",
                evidence=Evidence("No headings found", 1, 1, "document"),
                confidence=100,
                source="syntax-rule",
            )
        )
        return issues

    first_level, first_title, first_line = document.headings[0]
    if first_level != 1:
        issues.append(
            Issue(
                id="structure.title-not-h1",
                category="structure",
                rule_id="structure.title-check",
                severity=Severity.MEDIUM,
                message=f"First heading is H{first_level}, not H1.",
                recommendation="Use H1 for the document title.",
                evidence=Evidence(
                    f"First heading: H{first_level} '{first_title}'",
                    first_line, first_line, f"line {first_line}",
                ),
                confidence=100,
                source="syntax-rule",
                autofix_allowed=True,
            )
        )
    return issues


# ── Abstract Check ────────────────────────────────────────────────────────────

@rule(
    id="structure.abstract-check",
    category="structure",
    name="Abstract check",
    description="Checks for abstract/executive summary presence and quality.",
    severity=Severity.MEDIUM,
    priority=40,
    source="semantic-rule",
)
def abstract_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    min_words = config.get("min_abstract_words", 50)
    max_words = config.get("max_abstract_words", 350)

    # Find abstract-like headings
    abstract_headings = {"abstract", "executive summary", "tóm tắt"}
    abstract_found = False

    for level, title, line_no in document.headings:
        if title.strip().casefold() in abstract_headings:
            abstract_found = True
            # Estimate word count
            words_before_next = []
            for i in range(line_no, min(line_no + 80, len(document.lines))):
                line = document.lines[i].strip()
                if line and any(
                    h.title.strip().casefold() in abstract_headings
                    for _, h_title, _ in document.headings if h_title != title
                ):
                    break
                words_before_next.extend(line.split())
            word_count = len(words_before_next)

            if word_count < min_words:
                issues.append(
                    Issue(
                        id="structure.abstract-too-short",
                        category="structure",
                        rule_id="structure.abstract-check",
                        severity=Severity.MEDIUM,
                        message=f"Abstract/Summary is too short ({word_count} words, min: {min_words}).",
                        recommendation="Expand the abstract to adequately summarize the document.",
                        evidence=Evidence(
                            f"Abstract has {word_count} words",
                            line_no, line_no, f"line {line_no}",
                        ),
                        confidence=90,
                        source="semantic-rule",
                    )
                )
            elif word_count > max_words:
                issues.append(
                    Issue(
                        id="structure.abstract-too-long",
                        category="structure",
                        rule_id="structure.abstract-check",
                        severity=Severity.LOW,
                        message=f"Abstract/Summary is too long ({word_count} words, max: {max_words}).",
                        recommendation="Consider condensing the abstract.",
                        evidence=Evidence(
                            f"Abstract has {word_count} words",
                            line_no, line_no, f"line {line_no}",
                        ),
                        confidence=85,
                        source="semantic-rule",
                    )
                )
            break

    if not abstract_found and profile.id in ("academic", "business"):
        issues.append(
            Issue(
                id="structure.missing-abstract",
                category="structure",
                rule_id="structure.abstract-check",
                severity=Severity.HIGH,
                message=f"Missing abstract/executive summary (required for {profile.name} documents).",
                recommendation="Add a concise abstract (academic) or executive summary (business).",
                evidence=Evidence(
                    "No abstract or executive summary heading found",
                    1, 1, "document",
                ),
                confidence=100,
                source="syntax-rule",
            )
        )

    return issues


# ── Key Sections Check ────────────────────────────────────────────────────────

@rule(
    id="structure.key-sections-check",
    category="structure",
    name="Key academic sections check",
    description="Verifies presence of key sections: Introduction, Methodology, Results, Discussion, Conclusion.",
    severity=Severity.HIGH,
    priority=35,
    source="cross-rule",
)
def key_sections_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if profile.id != "academic":
        return issues

    seen_headings = set()
    for level, title, line_no in document.headings:
        seen_headings.add(title.strip().casefold())

    key_sections = {
        "introduction": ("Introduction", Severity.HIGH),
        "methodology": ("Methodology/Methods", Severity.HIGH),
        "conclusion": ("Conclusion", Severity.MEDIUM),
    }

    if profile.id == "academic":
        key_sections["results"] = ("Results/Findings", Severity.HIGH)
        key_sections["discussion"] = ("Discussion", Severity.MEDIUM)
        key_sections["references"] = ("References", Severity.HIGH)

    for section_key, (display_name, severity) in key_sections.items():
        found = any(section_key in h for h in seen_headings)
        if not found:
            # Check alternative names
            alt_names = {
                "methodology": {"method", "approach", "framework"},
                "results": {"experiment", "evaluation", "findings"},
                "conclusion": {"summary", "concluding remarks"},
                "references": {"bibliography", "works cited"},
            }
            found = bool(seen_headings & alt_names.get(section_key, set()))

        if not found:
            issues.append(
                Issue(
                    id=f"structure.missing-{section_key}",
                    category="structure",
                    rule_id="structure.key-sections-check",
                    severity=severity,
                    message=f"Missing key section: '{display_name}'.",
                    recommendation=f"Add a '{display_name}' section to ensure completeness.",
                    evidence=Evidence(
                        f"Required section '{display_name}' not found",
                        1, 1, "document",
                    ),
                    confidence=95,
                    source="cross-rule",
                )
            )

    return issues


# ── Section Order ─────────────────────────────────────────────────────────────

@rule(
    id="structure.section-order",
    category="structure",
    name="Section order check",
    description="Checks if academic sections appear in the correct logical order.",
    severity=Severity.MEDIUM,
    priority=30,
    source="cross-rule",
)
def section_order_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if profile.id != "academic":
        return issues

    # Expected order for academic papers
    expected_order = [
        "abstract", "introduction", "related work", "literature review",
        "methodology", "method", "approach",
        "results", "experiment", "evaluation", "findings",
        "discussion", "conclusion", "references", "bibliography",
        "appendix", "acknowledgment", "acknowledgement",
    ]

    # Find actual section order
    seen: list[tuple[str, int]] = []
    for level, title, line_no in document.headings:
        title_lower = title.strip().casefold()
        for expected in expected_order:
            if expected in title_lower or title_lower in expected:
                if expected not in [s for s, _ in seen]:
                    seen.append((expected, line_no))
                break

    # Check order
    for i in range(1, len(seen)):
        prev_section, prev_line = seen[i - 1]
        curr_section, curr_line = seen[i]
        prev_idx = expected_order.index(prev_section)
        curr_idx = expected_order.index(curr_section)
        if curr_idx < prev_idx:
            issues.append(
                Issue(
                    id=f"structure.wrong-order-{curr_section}",
                    category="structure",
                    rule_id="structure.section-order",
                    severity=Severity.MEDIUM,
                    message=f"Section '{curr_section.title()}' appears before '{prev_section.title()}'.",
                    recommendation=f"Reorder sections: '{prev_section.title()}' should come before '{curr_section.title()}'.",
                    evidence=Evidence(
                        f"'{curr_section.title()}' at line {curr_line}, '{prev_section.title()}' at line {prev_line}",
                        prev_line, curr_line, f"lines {prev_line}-{curr_line}",
                    ),
                    confidence=85,
                    source="cross-rule",
                )
            )

    # Check references position
    ref_found = any(
        h in seen for h in ["references", "bibliography"]
    )
    conclusion_found = "conclusion" in [s for s, _ in seen]

    if ref_found and conclusion_found:
        ref_line = next((l for s, l in seen if s in ("references", "bibliography")), 0)
        conc_line = next((l for s, l in seen if s == "conclusion"), 0)
        if ref_line < conc_line:
            issues.append(
                Issue(
                    id="structure.references-before-conclusion",
                    category="structure",
                    rule_id="structure.section-order",
                    severity=Severity.LOW,
                    message="References section appears before Conclusion.",
                    recommendation="Place the Conclusion section before the References.",
                    evidence=Evidence(
                        f"References at line {ref_line}, Conclusion at line {conc_line}",
                        conc_line, ref_line, f"lines {conc_line}-{ref_line}",
                    ),
                    confidence=80,
                    source="cross-rule",
                )
            )

    return issues


# ── Empty Section ─────────────────────────────────────────────────────────────

@rule(
    id="structure.empty-section",
    category="structure",
    name="Empty section detection",
    description="Detects sections with no or very little content.",
    severity=Severity.MEDIUM,
    priority=25,
    source="semantic-rule",
)
def empty_section_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    min_section_words = config.get("min_section_words", 10)

    heading_positions: list[tuple[int, str, int]] = [
        (level, title, line_no) for level, title, line_no in document.headings
    ]

    for i, (level, title, start_line) in enumerate(heading_positions):
        # Skip title (H1 at start)
        if i == 0 and level == 1:
            continue
        # Skip References/Bibliography
        if title.strip().casefold() in ("references", "bibliography", "appendix"):
            continue

        if i + 1 < len(heading_positions):
            end_line = heading_positions[i + 1][2]
        else:
            end_line = len(document.lines)

        # Count content words between headings (skip blank lines and other headings)
        content_lines = document.lines[start_line:end_line]
        content_words = []
        for line in content_lines:
            stripped = line.strip()
            if stripped and not any(
                stripped.casefold().startswith(h.casefold())
                for _, h, _ in document.headings if h != title
            ):
                content_words.extend(stripped.split())

        word_count = len(content_words)
        if word_count < min_section_words:
            issues.append(
                Issue(
                    id=f"structure.empty-section-{i}",
                    category="structure",
                    rule_id="structure.empty-section",
                    severity=Severity.MEDIUM,
                    message=f"Section '{title}' is nearly empty ({word_count} words).",
                    recommendation=f"Add content to the '{title}' section or remove it if not needed.",
                    evidence=Evidence(
                        f"'{title}' has only {word_count} words",
                        start_line, end_line, f"section starting at line {start_line}",
                    ),
                    confidence=95,
                    source="semantic-rule",
                )
            )

    return issues


# ── Duplicate Sections ───────────────────────────────────────────────────────

@rule(
    id="structure.duplicate-section",
    category="structure",
    name="Duplicate section detection",
    description="Detects sections with duplicate or very similar headings.",
    severity=Severity.MEDIUM,
    priority=20,
    source="syntax-rule",
)
def duplicate_section_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    seen: dict[str, list[int]] = {}

    for level, title, line_no in document.headings:
        key = title.strip().casefold()
        if key not in seen:
            seen[key] = []
        seen[key].append(line_no)

    for title, lines in seen.items():
        if len(lines) > 1:
            issues.append(
                Issue(
                    id=f"structure.duplicate-section-{title.replace(' ', '-')}",
                    category="structure",
                    rule_id="structure.duplicate-section",
                    severity=Severity.MEDIUM,
                    message=f"Duplicate section heading: '{title.title()}' found {len(lines)} times.",
                    recommendation="Rename or merge the duplicate sections.",
                    evidence=Evidence(
                        f"'{title.title()}' at lines: {', '.join(str(l) for l in lines)}",
                        lines[0], lines[-1], f"lines {lines[0]}, {lines[-1]}",
                    ),
                    confidence=100,
                    source="syntax-rule",
                )
            )

    return issues


# ── Section Length Check ──────────────────────────────────────────────────────

@rule(
    id="structure.section-length-variance",
    category="structure",
    name="Section length variance",
    description="Flags unusually large variance in section lengths.",
    severity=Severity.LOW,
    priority=15,
    source="semantic-rule",
)
def section_length_variance(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    ratio_threshold = config.get("variance_ratio", 10)

    heading_positions: list[tuple[int, str, int]] = [
        (level, title, line_no) for level, title, line_no in document.headings
    ]
    if len(heading_positions) < 3:
        return issues

    # Calculate words per section
    section_sizes: list[tuple[str, int]] = []
    for i, (level, title, start_line) in enumerate(heading_positions):
        if i + 1 < len(heading_positions):
            end_line = heading_positions[i + 1][2]
        else:
            end_line = len(document.lines)
        words = len(" ".join(document.lines[start_line:end_line]).split())
        section_sizes.append((title, words))

    if not section_sizes:
        return issues

    sizes = [s for _, s in section_sizes]
    avg_size = sum(sizes) / len(sizes)
    if avg_size < 20:
        return issues

    for title, size in section_sizes:
        if size > avg_size * ratio_threshold:
            issues.append(
                Issue(
                    id=f"structure.section-too-large-{title[:20].replace(' ', '-')}",
                    category="structure",
                    rule_id="structure.section-length-variance",
                    severity=Severity.LOW,
                    message=f"Section '{title}' is {size} words — {size / avg_size:.1f}x the average ({avg_size:.0f}).",
                    recommendation="Consider splitting into sub-sections or condensing.",
                    evidence=Evidence(
                        f"'{title}': {size} words",
                        1, 1, f"section '{title}'",
                    ),
                    confidence=70,
                    source="semantic-rule",
                )
            )

    return issues


# ── Missing Keywords (Academic) ───────────────────────────────────────────────

@rule(
    id="structure.keywords-check",
    category="structure",
    name="Keywords section check",
    description="Checks for keywords section in academic documents.",
    severity=Severity.LOW,
    priority=10,
    source="syntax-rule",
    pack_id="apa",
)
def keywords_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if profile.id != "academic":
        return issues

    keywords_found = False
    for level, title, line_no in document.headings:
        if "keyword" in title.strip().casefold():
            keywords_found = True
            # Check if keywords are actually provided (not empty)
            if line_no < len(document.lines) - 1:
                next_line = document.lines[line_no].strip()
                if not next_line or next_line.startswith("#"):
                    issues.append(
                        Issue(
                            id="structure.keywords-empty",
                            category="structure",
                            rule_id="structure.keywords-check",
                            severity=Severity.LOW,
                            message="Keywords section is empty.",
                            recommendation="Add 4-6 keywords that represent the main topics of your paper.",
                            evidence=Evidence(
                                "Empty keywords section",
                                line_no, line_no, f"line {line_no}",
                            ),
                            confidence=100,
                            source="syntax-rule",
                        )
                    )
            break

    if not keywords_found:
        issues.append(
            Issue(
                id="structure.missing-keywords",
                category="structure",
                rule_id="structure.keywords-check",
                severity=Severity.LOW,
                message="No 'Keywords' section found (recommended for academic papers).",
                recommendation="Add a 'Keywords' section after the abstract with 4-6 key terms.",
                evidence=Evidence(
                    "Keywords section not found",
                    1, 1, "document",
                ),
                confidence=90,
                source="syntax-rule",
            )
        )

    return issues


# ── SOP Specific Structure ────────────────────────────────────────────────────

@rule(
    id="structure.sop-required-fields",
    category="structure",
    name="SOP required fields check",
    description="Verifies SOP documents have purpose, scope, procedure, and approval sections.",
    severity=Severity.HIGH,
    priority=35,
    source="cross-rule",
    pack_id="sop",
)
def sop_required_fields(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if profile.id != "sop":
        return issues

    seen = {title.strip().casefold() for _, title, _ in document.headings}

    sop_requirements = [
        ("purpose", "Purpose", Severity.HIGH),
        ("scope", "Scope", Severity.HIGH),
        ("procedure", "Procedure", Severity.HIGH),
    ]

    for key, display, severity in sop_requirements:
        if key not in seen and key + "s" not in seen:
            issues.append(
                Issue(
                    id=f"structure.sop-missing-{key}",
                    category="structure",
                    rule_id="structure.sop-required-fields",
                    severity=severity,
                    message=f"Missing required SOP section: '{display}'.",
                    recommendation=f"SOP documents must include a '{display}' section.",
                    evidence=Evidence(
                        f"Required SOP section '{display}' not found",
                        1, 1, "document",
                    ),
                    confidence=100,
                    source="cross-rule",
                )
            )

    return issues
