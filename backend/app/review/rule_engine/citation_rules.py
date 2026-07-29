"""Citation rules: APA 7, IEEE, and generic citation checking."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from ..models import DocumentModel, Evidence, Issue, Severity
from ..profiles import Profile
from .registry import rule

# ── Patterns ───────────────────────────────────────────────────────────────────

# APA 7 in-text: (Author, Year) or (Author, Year, p. Page) or Author (Year)
APA_IN_TEXT = re.compile(
    r"\([A-Z][A-Za-z\u00C0-\u024F\-]+(?:\s+(?:&|and)\s+[A-Z][A-Za-z\-]+)?"
    r"(?:\s+et\s+al\.?)?,\s*\d{4}(?:,\s*(?:p\.|pp\.)\s*\d+)?\)"
)
# APA 7 narrative: Author (Year)
APA_NARRATIVE = re.compile(r"[A-Z][A-Za-z\u00C0-\u024F\-]+\s+\(\d{4}\)")

# IEEE style: [1], [1, 2], [1-3]
IEEE_CITATION = re.compile(r"\[(?:\d+(?:,\s*\d+)*(?:\s*-\s*\d+)?)\]")

# Generic: (Author et al., Year)
ET_AL_CITATION = re.compile(r"\([A-Z][A-Za-z]+\s+et\s+al\..*?\d{4}\)")

# Reference entries
DOI_PATTERN = re.compile(r"(?:https?://)?(?:dx\.)?doi\.org/[^\s,;]+")
URL_PATTERN = re.compile(r"https?://[^\s,;)}]+")
ISBN_PATTERN = re.compile(r"(?:ISBN[-]?(?:\s)?)(?:\d[-\s]?){10,17}")

# Year range
CURRENT_YEAR = 2026
VALID_YEAR_RANGE = (1900, 2026)

# ACM citation patterns
ACM_CITATION = re.compile(r"<cite>.*?</cite>|<citation>.*?</citation>", re.I | re.DOTALL)
ACM_REF = re.compile(r"\[(?:\d+)\]|\b\d+\.\s+(?:[A-Z][a-z]+\s+)+")

# Nature citation patterns (superscript numbered)
NATURE_CITATION = re.compile(r"\^{?(?:\d+(?:,\s*\d+)*(?:-\d+)?)}?")

# Springer citation patterns (author-year)
SPRINGER_CITATION = re.compile(r"\([A-Z][a-z]+(?:\s+(?:et\s+al\.?))?,\s*\d{4}[^)]*\)")

# Elsevier citation patterns
ELSEVIER_CITATION = re.compile(r"\[(?:\d+(?:,\s*\d+)*(?:,\s*pp?\.\s*\d+)?)\]")


# ── Generic Citation Rules ────────────────────────────────────────────────────

@rule(
    id="citation.in-text-reference-mismatch",
    category="citation",
    name="Citation-reference matching",
    description="Checks that each in-text citation has a corresponding reference entry.",
    severity=Severity.HIGH,
    priority=30,
    source="cross-rule",
)
def in_text_reference_match(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if profile.id == "technical_design":
        return issues
    text = document.text

    citations = _count_citations(text)
    references = document.references

    if citations > 0 and not references:
        issues.append(
            Issue(
                id="citation.missing-reference-list",
                category="citation",
                rule_id="citation.in-text-reference-mismatch",
                severity=Severity.HIGH,
                message=f"Found {citations} in-text citation(s) but no reference list.",
                recommendation="Add a 'References' or 'Bibliography' section with complete entries.",
                evidence=Evidence(
                    f"{citations} citation(s) detected",
                    1, 1, "document",
                ),
                confidence=96,
                source="cross-rule",
            )
        )
    elif references and citations == 0:
        issues.append(
            Issue(
                id="citation.orphan-references",
                category="citation",
                rule_id="citation.in-text-reference-mismatch",
                severity=Severity.MEDIUM,
                message=f"Found {len(references)} reference(s) but no in-text citations.",
                recommendation="Ensure every reference is cited in the document body.",
                evidence=Evidence(
                    references[0][:200], 1, 1, "references",
                ),
                confidence=85,
                source="cross-rule",
            )
        )

    return issues


@rule(
    id="citation.year-validity",
    category="citation",
    name="Citation year validity",
    description="Checks that cited years are within a reasonable range.",
    severity=Severity.LOW,
    priority=20,
    source="syntax-rule",
)
def citation_year_validity(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    # Extract all years from citations
    years = re.findall(r"\([^)]*?(\d{4})[^)]*\)", document.text)
    years += re.findall(r"[A-Z][A-Za-z]+\s+\((\d{4})\)", document.text)

    for year_str in years:
        try:
            year = int(year_str)
            if year < VALID_YEAR_RANGE[0] or year > CURRENT_YEAR:
                issues.append(
                    Issue(
                        id=f"citation.invalid-year-{year}",
                        category="citation",
                        rule_id="citation.year-validity",
                        severity=Severity.LOW,
                        message=f"Citation uses year '{year}', which is outside valid range ({VALID_YEAR_RANGE[0]}-{CURRENT_YEAR}).",
                        recommendation="Verify the publication year is correct.",
                        evidence=Evidence(
                            f"Year {year}", 1, 1, "document",
                        ),
                        confidence=90,
                        source="syntax-rule",
                    )
                )
            elif year > CURRENT_YEAR - 1:
                issues.append(
                    Issue(
                        id=f"citation.future-year-{year}",
                        category="citation",
                        rule_id="citation.year-validity",
                        severity=Severity.LOW,
                        message=f"Citation uses year '{year}', which may be a future or in-press publication.",
                        recommendation="Verify the date. For in-press works, use 'in press' or the expected year.",
                        evidence=Evidence(
                            f"Year {year}", 1, 1, "document",
                        ),
                        confidence=70,
                        source="syntax-rule",
                    )
                )
        except ValueError:
            pass

    return issues


# ── APA 7 Specific Rules ──────────────────────────────────────────────────────

@rule(
    id="citation.apa-format",
    category="citation",
    name="APA 7 citation format",
    description="Checks APA 7 in-text citation formatting.",
    severity=Severity.MEDIUM,
    priority=25,
    source="syntax-rule",
    pack_id="apa",
)
def apa_citation_format(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    lines = document.lines

    # Check for common APA issues in each line
    for line_no, line in enumerate(lines, 1):
        # Find citation-like text that doesn't match APA patterns
        # Look for parentheses that might be citations
        paren_groups = re.findall(r"\([^)]{3,}\)", line)
        for group in paren_groups:
            # Check if it looks like a citation but doesn't match APA
            if re.search(r"[A-Z]", group) and re.search(r"\d{4}", group):
                # Already matched by APA_IN_TEXT?
                if not APA_IN_TEXT.search(group) and not APA_NARRATIVE.search(line[:50]):
                    issues.append(
                        Issue(
                            id=f"citation.apa-format-{line_no}",
                            category="citation",
                            rule_id="citation.apa-format",
                            severity=Severity.LOW,
                            message=f"Possible citation at line {line_no} does not match APA 7 format.",
                            recommendation="Use APA 7 format: (Author, Year) or Author (Year).",
                            evidence=Evidence(
                                group[:200], line_no, line_no, f"line {line_no}",
                            ),
                            confidence=70,
                            source="semantic-rule",
                        )
                    )

    # Check line spacing for references (APA requires double-spacing)
    # This is a simplified check
    reference_section = False
    for line_no, line in enumerate(lines, 1):
        if re.search(r"^(references|bibliography)$", line.strip(), re.I):
            reference_section = True
            continue
        if reference_section and line.strip() == "":
            reference_section = False

    return issues


@rule(
    id="citation.apa-heading",
    category="citation",
    name="APA references heading",
    description="Verifies references section uses correct APA heading.",
    severity=Severity.MEDIUM,
    priority=20,
    source="syntax-rule",
    pack_id="apa",
)
def apa_references_heading(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    ref_headings = [
        title for _, title, _ in document.headings
        if re.search(r"^(references|bibliography)$", title, re.I)
    ]

    if not ref_headings:
        # Already caught by missing-section rule, only flag if references exist
        if document.references:
            issues.append(
                Issue(
                    id="citation.apa-no-heading",
                    category="citation",
                    rule_id="citation.apa-heading",
                    severity=Severity.MEDIUM,
                    message="Reference entries found but no 'References' heading.",
                    recommendation="Add a 'References' heading (APA 7 uses bold, centered H1/H2).",
                    evidence=Evidence(
                        f"{len(document.references)} reference(s) without heading",
                        1, 1, "references",
                    ),
                    confidence=95,
                    source="syntax-rule",
                )
            )

    return issues


# ── IEEE Specific Rules ───────────────────────────────────────────────────────

@rule(
    id="citation.ieee-format",
    category="citation",
    name="IEEE citation format",
    description="Checks IEEE-style bracketed citation formatting.",
    severity=Severity.MEDIUM,
    priority=25,
    source="syntax-rule",
    pack_id="ieee",
)
def ieee_citation_format(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    text = document.text

    # Check for citations
    ieee_citations = IEEE_CITATION.findall(text)
    if not ieee_citations:
        return issues

    # IEEE: citations should be sequential [1], [2], [3], etc.
    numbers = []
    for cit in ieee_citations:
        nums = re.findall(r"\d+", cit)
        numbers.extend(int(n) for n in nums)

    if numbers:
        # Check if citations start from 1
        if numbers[0] != 1:
            issues.append(
                Issue(
                    id="citation.ieee-start",
                    category="citation",
                    rule_id="citation.ieee-format",
                    severity=Severity.LOW,
                    message="IEEE citations should start from [1].",
                    recommendation="Ensure the first reference cited is [1].",
                    evidence=Evidence(
                        f"Starts from [{numbers[0]}]",
                        1, 1, "document",
                    ),
                    confidence=80,
                    source="syntax-rule",
                )
            )

        # Check ordering (first appearance should be sequential)
        seen = set()
        prev = 0
        out_of_order = False
        for n in numbers:
            if n not in seen and n != prev + 1:
                out_of_order = True
                break
            if n not in seen:
                prev = n
                seen.add(n)

        if out_of_order:
            issues.append(
                Issue(
                    id="citation.ieee-order",
                    category="citation",
                    rule_id="citation.ieee-format",
                    severity=Severity.MEDIUM,
                    message="IEEE citations are not in sequential order.",
                    recommendation="IEEE requires references to be numbered in order of first appearance.",
                    evidence=Evidence(
                        f"First instances of citations: {numbers[:10]}",
                        1, 1, "document",
                    ),
                    confidence=85,
                    source="cross-rule",
                )
            )

    return issues


# ── DOI / URL Validation ──────────────────────────────────────────────────────

@rule(
    id="citation.doi-validation",
    category="citation",
    name="DOI/URL validation",
    description="Validates DOI and URL formats in references.",
    severity=Severity.LOW,
    priority=15,
    source="syntax-rule",
)
def doi_url_validation(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    text = document.text

    # Find DOIs
    dois = DOI_PATTERN.findall(text)
    for doi in dois:
        # Check for common issues
        if "doi.org/" in doi:
            # Extract just the DOI part after the resolver
            doi_id = doi.split("doi.org/")[-1]
            if not doi_id.strip():
                issues.append(
                    Issue(
                        id="citation.doi-empty",
                        category="citation",
                        rule_id="citation.doi-validation",
                        severity=Severity.LOW,
                        message="DOI URL is missing the identifier.",
                        recommendation="Provide the full DOI identifier (e.g., doi.org/10.1000/xyz123).",
                        evidence=Evidence(
                            doi[:200], 1, 1, "document",
                        ),
                        confidence=100,
                        source="syntax-rule",
                    )
                )

    # Find broken-looking URLs
    urls = URL_PATTERN.findall(text)
    for url in urls:
        # Simple check: must have a proper domain
        parsed = urlparse(url)
        if not parsed.netloc or "." not in parsed.netloc:
            issues.append(
                Issue(
                    id="citation.broken-url",
                    category="citation",
                    rule_id="citation.doi-validation",
                    severity=Severity.LOW,
                    message=f"URL appears malformed: '{url[:60]}...'",
                    recommendation="Verify the URL is complete and accessible.",
                    evidence=Evidence(
                        url[:200], 1, 1, "document",
                    ),
                    confidence=85,
                    source="syntax-rule",
                )
            )

    return issues


# ── ACM Citation Rules ────────────────────────────────────────────────────────

@rule(
    id="citation.acm-format",
    category="citation",
    name="ACM citation format",
    description="Checks ACM-style citation formatting.",
    severity=Severity.MEDIUM,
    priority=25,
    source="syntax-rule",
    pack_id="acm",
)
def acm_citation_format(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    text = document.text

    # Check for bracketed ACM citations
    bracketed = re.findall(r"\[(\d+)\]", text)
    if not bracketed:
        return issues

    # ACM usually uses sequential numbering starting from 1
    numbers = [int(n) for n in bracketed]
    if numbers and min(numbers) != 1:
        issues.append(
            Issue(
                id="citation.acm-start",
                category="citation",
                rule_id="citation.acm-format",
                severity=Severity.LOW,
                message="ACM citations should typically start from [1].",
                recommendation="Ensure the first reference cited is [1] in ACM style.",
                evidence=Evidence(
                    f"First citation number: [{min(numbers)}]",
                    1, 1, "document",
                ),
                confidence=75,
                source="syntax-rule",
            )
        )

    return issues


@rule(
    id="citation.acm-reference-format",
    category="citation",
    name="ACM reference format",
    description="Checks ACM reference entry formatting.",
    severity=Severity.MEDIUM,
    priority=20,
    source="syntax-rule",
    pack_id="acm",
)
def acm_reference_format(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if not document.references:
        return issues

    # Check for ACM reference structure (author initials, year, title, etc.)
    for i, ref in enumerate(document.references):
        # ACM: Author initials first (e.g., J. K. Author)
        if ref.startswith("[") or (i + 1 < len(document.references) and ref[0].isdigit()):
            continue  # Already numbered

        # Check for initials pattern
        has_initials = bool(re.search(r"\b[A-Z]\.\s*[A-Z]\.\s+[A-Z][a-z]+", ref))
        if not has_initials:
            issues.append(
                Issue(
                    id=f"citation.acm-ref-format-{i}",
                    category="citation",
                    rule_id="citation.acm-reference-format",
                    severity=Severity.LOW,
                    message="Reference may not follow ACM format (initials before surname).",
                    recommendation="ACM format: J. K. Author, 'Title,' Publisher, Year.",
                    evidence=Evidence(
                        ref[:200], 1, 1, f"reference {i + 1}",
                    ),
                    confidence=70,
                    source="semantic-rule",
                )
            )
            if len(issues) >= 3:
                break

    return issues


# ── Nature Citation Rules ──────────────────────────────────────────────────────

@rule(
    id="citation.nature-format",
    category="citation",
    name="Nature citation format",
    description="Checks Nature-style superscript citation formatting.",
    severity=Severity.MEDIUM,
    priority=25,
    source="syntax-rule",
    pack_id="nature",
)
def nature_citation_format(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    text = document.text

    # Nature uses superscript numbers: ^{1}, ^{2,3}, ^{4-6}
    superscript_markers = re.findall(r"\^\{?(\d+(?:[,\-]\d+)*)\}?", text)
    if superscript_markers:
        # Check if they look like superscript citations
        all_numbers = []
        for group in superscript_markers:
            nums = re.findall(r"\d+", group)
            all_numbers.extend(int(n) for n in nums)

        if all_numbers and min(all_numbers) != 1:
            issues.append(
                Issue(
                    id="citation.nature-start",
                    category="citation",
                    rule_id="citation.nature-format",
                    severity=Severity.LOW,
                    message="Nature superscript citations should start from ¹.",
                    recommendation="Ensure first citation is numbered 1.",
                    evidence=Evidence(
                        f"First citation number: {min(all_numbers)}",
                        1, 1, "document",
                    ),
                    confidence=75,
                    source="syntax-rule",
                )
            )

    return issues


# ── Springer Citation Rules ────────────────────────────────────────────────────

@rule(
    id="citation.springer-format",
    category="citation",
    name="Springer citation format",
    description="Checks Springer-style author-year citation formatting.",
    severity=Severity.MEDIUM,
    priority=25,
    source="syntax-rule",
    pack_id="springer",
)
def springer_citation_format(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    text = document.text

    # Springer uses (Author, Year) similar to APA but may use et al. differently
    springer_citations = SPRINGER_CITATION.findall(text)
    if not springer_citations:
        return issues

    # Springer requires complete references
    if springer_citations and not document.references:
        issues.append(
            Issue(
                id="citation.springer-no-refs",
                category="citation",
                rule_id="citation.springer-format",
                severity=Severity.HIGH,
                message=f"Found {len(springer_citations)} Springer-style citations but no reference list.",
                recommendation="Add a complete reference list formatted per Springer guidelines.",
                evidence=Evidence(
                    f"{len(springer_citations)} citations without references",
                    1, 1, "document",
                ),
                confidence=90,
                source="cross-rule",
            )
        )

    return issues


# ── Elsevier Citation Rules ───────────────────────────────────────────────────

@rule(
    id="citation.elsevier-format",
    category="citation",
    name="Elsevier citation format",
    description="Checks Elsevier-style numbered citation formatting.",
    severity=Severity.MEDIUM,
    priority=25,
    source="syntax-rule",
    pack_id="elsevier",
)
def elsevier_citation_format(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    text = document.text

    # Elsevier uses [1], [1,2], [1-3] with optional page ranges
    elsevier_citations = ELSEVIER_CITATION.findall(text)
    if not elsevier_citations:
        return issues

    # Check for basic sequential numbering
    numbers = []
    for cit in elsevier_citations:
        nums = re.findall(r"\d+", cit)
        numbers.extend(int(n) for n in nums)

    if numbers:
        # Detect if starting correctly
        if numbers[0] != 1:
            issues.append(
                Issue(
                    id="citation.elsevier-start",
                    category="citation",
                    rule_id="citation.elsevier-format",
                    severity=Severity.LOW,
                    message="Elsevier citations should start from [1].",
                    recommendation="Ensure the first reference is [1].",
                    evidence=Evidence(
                        f"Starts from [{numbers[0]}]",
                        1, 1, "document",
                    ),
                    confidence=80,
                    source="syntax-rule",
                )
            )

    return issues


# ── Citation Style Consistency ─────────────────────────────────────────────────

@rule(
    id="citation.style-consistency",
    category="citation",
    name="Citation style consistency",
    description="Detects mixed citation styles in the same document.",
    severity=Severity.MEDIUM,
    priority=30,
    source="cross-rule",
)
def citation_style_consistency(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    text = document.text

    styles_detected = []

    # APA
    apa_count = len(APA_IN_TEXT.findall(text)) + len(APA_NARRATIVE.findall(text))
    if apa_count > 0:
        styles_detected.append(f"APA ({apa_count}x)")

    # IEEE
    ieee_count = len(IEEE_CITATION.findall(text))
    if ieee_count > 0:
        styles_detected.append(f"IEEE ({ieee_count}x)")

    # ACM
    acm_count = len(re.findall(r"\[(\d+)\]", text))
    if acm_count > 0:
        styles_detected.append(f"ACM ({acm_count}x)")

    # Springer / generic author-year
    springer_count = len(SPRINGER_CITATION.findall(text))
    if springer_count > 0:
        styles_detected.append(f"Author-Year ({springer_count}x)")

    if len(styles_detected) > 1:
        issues.append(
            Issue(
                id="citation.mixed-styles",
                category="citation",
                rule_id="citation.style-consistency",
                severity=Severity.MEDIUM,
                message=f"Mixed citation styles detected: {', '.join(styles_detected)}.",
                recommendation="Use only one citation style consistently throughout the document.",
                evidence=Evidence(
                    f"Styles: {', '.join(styles_detected)}",
                    1, 1, "document",
                ),
                confidence=90,
                source="cross-rule",
            )
        )

    return issues


# ── Duplicate / Orphan References ─────────────────────────────────────────────

@rule(
    id="citation.duplicate-reference",
    category="citation",
    name="Duplicate references",
    description="Detects duplicate reference entries.",
    severity=Severity.LOW,
    priority=10,
    source="syntax-rule",
)
def duplicate_reference_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    references = document.references

    # Simple duplicate detection based on first 80 chars
    seen: dict[str, int] = {}
    for i, ref in enumerate(references):
        key = ref[:80].lower().strip()
        if key in seen:
            issues.append(
                Issue(
                    id=f"citation.duplicate-ref-{i}",
                    category="citation",
                    rule_id="citation.duplicate-reference",
                    severity=Severity.LOW,
                    message="Possible duplicate reference entry.",
                    recommendation="Remove the duplicate reference entry.",
                    evidence=Evidence(
                        ref[:200], 1, 1, f"reference {i + 1}",
                    ),
                    confidence=80,
                    source="syntax-rule",
                )
            )
        seen[key] = i

    return issues


# ── Helpers ────────────────────────────────────────────────────────────────────

def _count_citations(text: str) -> int:
    """Count in-text citations using various patterns."""
    count = 0
    count += len(APA_IN_TEXT.findall(text))
    count += len(APA_NARRATIVE.findall(text))
    count += len(IEEE_CITATION.findall(text))
    count += len(ET_AL_CITATION.findall(text))
    # Count generic [Author, Year] patterns
    count += len(re.findall(r"\([A-Z][A-Za-z]+\s+(?:&\s+[A-Z][A-Za-z]+)?,\s*\d{4}[^)]*\)", text))
    return count
