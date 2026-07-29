"""Logic and consistency rules: undefined acronyms, contradictions, transitions, scope."""

from __future__ import annotations

import re
from typing import Any

from ..models import DocumentModel, Evidence, Issue, Severity
from ..profiles import Profile
from .registry import rule

# ── Patterns ───────────────────────────────────────────────────────────────────

# Acronym patterns
ACRONYM_DEFINITION = re.compile(
    r"\(([A-Z]{2,}(?:/[A-Z]+)?)\)"  # (AI), (NLP), (XML/HTML)
)
ACRONYM_IN_TEXT = re.compile(r"\b[A-Z]{2,}\b")  # AI, NLP, CNN

# Common transition words
TRANSITION_WORDS = {
    "however", "therefore", "moreover", "furthermore", "nevertheless",
    "consequently", "additionally", "thus", "hence", "accordingly",
    "meanwhile", "subsequently", "notably", "specifically", "conversely",
    "in contrast", "on the other hand", "in addition", "as a result",
    "for example", "for instance", "in particular", "first", "second",
    "third", "finally", "lastly", "then", "next",
}


# ── Undefined Acronyms ────────────────────────────────────────────────────────

@rule(
    id="logic.undefined-acronym",
    category="logic",
    name="Undefined acronym detection",
    description="Finds acronyms used before being defined.",
    severity=Severity.MEDIUM,
    priority=30,
    source="cross-rule",
)
def undefined_acronym_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []

    # Collect all acronym definitions
    defined_acronyms: dict[str, int] = {}
    for line_no, line in enumerate(document.lines, 1):
        for match in ACRONYM_DEFINITION.finditer(line):
            acronym = match.group(1)
            # Definition typically before the acronym in parentheses
            defined_acronyms[acronym] = line_no

    # Check for acronyms used but never defined
    # Exclude common short words that aren't acronyms
    exclude = {"THE", "FOR", "AND", "ARE", "NOT", "BUT", "ITS", "ALL",
               "CAN", "WILL", "HAS", "HAD", "WAS", "WERE", "DOES", "BEEN",
               "THAT", "THIS", "WITH", "FROM", "HAVE", "BEEN", "MORE", "SOME",
               "THAN", "ALSO", "SUCH", "ONLY", "JUST", "MOST", "EACH", "BOTH"}

    for line_no, line in enumerate(document.lines, 1):
        for match in ACRONYM_IN_TEXT.finditer(line):
            acronym = match.group(0)
            if acronym in exclude or len(acronym) < 2 or len(acronym) > 8:
                continue
            # Skip if it looks like a word (has vowels, not all caps)
            if not acronym.isupper():
                continue
            # Skip if it was defined
            if acronym in defined_acronyms:
                continue
            # Check if it's actually an uppercase word (not acronym)
            if acronym.lower() in {
                "the", "for", "and", "are", "but", "its", "all",
                "can", "has", "had", "was", "were", "not",
            }:
                continue

            issues.append(
                Issue(
                    id=f"logic.undefined-acronym-{acronym}",
                    category="logic",
                    rule_id="logic.undefined-acronym",
                    severity=Severity.MEDIUM,
                    message=f"Acronym '{acronym}' used without being defined (line {line_no}).",
                    recommendation=f"Define '{acronym}' on first use: '... (acronym)'.",
                    evidence=Evidence(
                        line[:200], line_no, line_no, f"line {line_no}",
                    ),
                    confidence=85,
                    source="cross-rule",
                )
            )

    return issues


# ── Missing Transitions ───────────────────────────────────────────────────────

@rule(
    id="logic.missing-transition",
    category="logic",
    name="Missing transition detection",
    description="Detects abrupt paragraph transitions.",
    severity=Severity.LOW,
    priority=15,
    source="semantic-rule",
)
def missing_transition_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    min_paragraph_lines = config.get("min_paragraph_lines", 3)

    # Group lines into paragraphs (separated by blank lines)
    paragraphs: list[list[str]] = []
    current: list[str] = []
    for line in document.lines:
        if line.strip() == "":
            if current:
                paragraphs.append(current)
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(current)

    # Check transitions between paragraphs
    for i in range(1, len(paragraphs)):
        prev_text = " ".join(paragraphs[i - 1]).lower()
        curr_text = paragraphs[i][0].lower() if paragraphs[i] else ""

        # Check if current paragraph starts with a transition word
        starts_with_transition = any(
            curr_text.startswith(tw) for tw in TRANSITION_WORDS
        )

        if not starts_with_transition and len(paragraphs[i]) >= min_paragraph_lines:
            # Rough line number estimate
            line_no = sum(len(p) for p in paragraphs[:i]) + 1
            issues.append(
                Issue(
                    id=f"logic.missing-transition-{i}",
                    category="logic",
                    rule_id="logic.missing-transition",
                    severity=Severity.LOW,
                    message="Paragraph may need a transition from the previous one.",
                    recommendation="Start with a transition word (e.g., 'However', 'Therefore', 'Furthermore') or a bridging sentence.",
                    evidence=Evidence(
                        curr_text[:200], line_no, line_no, f"paragraph {i + 1}",
                    ),
                    confidence=60,
                    source="semantic-rule",
                )
            )

    return issues


# ── Duplicate Content ─────────────────────────────────────────────────────────

@rule(
    id="logic.duplicate-content",
    category="logic",
    name="Duplicate content detection",
    description="Finds highly similar paragraphs that may be duplicates.",
    severity=Severity.MEDIUM,
    priority=20,
    source="semantic-rule",
)
def duplicate_content_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    similarity_threshold = config.get("similarity_threshold", 0.8)

    # Simple fingerprint-based duplicate detection
    seen_fingerprints: dict[int, int] = {}  # hash -> line_no
    for line_no, line in enumerate(document.lines, 1):
        words = re.findall(r"\b\w+\b", line.lower())
        if len(words) < 5:
            continue
        # Create a simple fingerprint from significant words
        significant = [w for w in words if len(w) > 3]
        fingerprint = hash(tuple(significant[:10]))
        if fingerprint in seen_fingerprints:
            prev_line = seen_fingerprints[fingerprint]
            issues.append(
                Issue(
                    id=f"logic.duplicate-{line_no}",
                    category="logic",
                    rule_id="logic.duplicate-content",
                    severity=Severity.MEDIUM,
                    message="Possible duplicate content detected.",
                    recommendation="Review and remove or rephrase the duplicate content.",
                    evidence=Evidence(
                        line[:200], line_no, line_no, f"line {line_no}",
                    ),
                    confidence=75,
                    source="semantic-rule",
                )
            )
            if len(issues) >= 5:  # Limit duplicates
                break
        else:
            seen_fingerprints[fingerprint] = line_no

    return issues


# ── Scope Mismatch ────────────────────────────────────────────────────────────

@rule(
    id="logic.scope-mismatch",
    category="logic",
    name="Scope consistency check",
    description="Checks for scope mismatches between sections.",
    severity=Severity.MEDIUM,
    priority=10,
    source="semantic-rule",
)
def scope_mismatch_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []

    # Check if Conclusion/Summary section references content not in document
    conclusion_text = ""
    in_conclusion = False
    for line_no, line in enumerate(document.lines, 1):
        if re.search(r"^(conclusion|summary|discussion|kết luận)", line.strip(), re.I):
            in_conclusion = True
            continue
        if in_conclusion:
            if re.search(r"^(introduction|methodology|references)", line.strip(), re.I):
                in_conclusion = False
                continue
            conclusion_text += line + " "

    if conclusion_text:
        # Check if conclusion references specific terms not used earlier
        important_terms = re.findall(r"\b[A-Z][a-z]{3,}\b", conclusion_text)
        body_text = " ".join(document.lines[:len(document.lines) // 2])

        for term in important_terms[:5]:
            if term.lower() not in body_text.lower():
                issues.append(
                    Issue(
                        id=f"logic.scope-new-term-{term.lower()}",
                        category="logic",
                        rule_id="logic.scope-mismatch",
                        severity=Severity.LOW,
                        message=f"Term '{term}' appears in conclusion but not in the main body.",
                        recommendation="Ensure all key terms introduced in the conclusion are discussed earlier.",
                        evidence=Evidence(
                            f"'{term}' found only in conclusion section",
                            1, 1, "conclusion",
                        ),
                        confidence=65,
                        source="semantic-rule",
                    )
                )

    return issues


# ── Contradictory Statements ───────────────────────────────────────────────────

@rule(
    id="logic.contradictions",
    category="logic",
    name="Contradictory statements",
    description="Detects potentially contradictory statements in the document.",
    severity=Severity.HIGH,
    priority=25,
    source="semantic-rule",
)
def contradictions_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    text_lower = document.text.lower()

    # Common contradiction patterns
    contradiction_pairs = [
        (r"\b(always|never)\b", r"\b(sometimes|occasionally|rarely)\b", "always/never")
    ]

    # Check for statistical contradictions (e.g., "100%" vs "some")
    absolute_numbers = re.findall(r"\b(?:100%|all|every|none|no|zero|entirely|completely)\b", text_lower)
    qualifiers = re.findall(r"\b(some|most|many|few|several|partially|partly|approximately|about|nearly)\b", text_lower)

    if absolute_numbers and qualifiers:
        # Detect if they appear in different parts of the document
        absolute_lines = set()
        qualifier_lines = set()
        for i, line in enumerate(document.lines):
            line_lower = line.lower()
            if any(re.search(rf"\b{re.escape(w)}\b", line_lower) for w in absolute_numbers[:3]):
                absolute_lines.add(i)
            if any(re.search(rf"\b{re.escape(w)}\b", line_lower) for w in qualifiers[:3]):
                qualifier_lines.add(i)

        # Only flag if the same section has both
        same_section = absolute_lines & qualifier_lines
        if same_section:
            for line_no in list(same_section)[:3]:
                issues.append(
                    Issue(
                        id=f"logic.contradiction-abs-qual-{line_no}",
                        category="logic",
                        rule_id="logic.contradictions",
                        severity=Severity.HIGH,
                        message="Possible contradiction: uses absolutist language and qualifiers in the same section.",
                        recommendation="Ensure statements are consistent: either absolute (all, none) or qualified (some, most), not both.",
                        evidence=Evidence(
                            document.lines[line_no][:200],
                            line_no + 1, line_no + 1, f"line {line_no + 1}",
                        ),
                        confidence=60,
                        source="semantic-rule",
                    )
                )

    # Check for "In contrast" vs "Similarly" contradictions near each other
    contrast_markers = re.finditer(r"\bin\s+contrast\b|\bconversely\b|\bhowever\b|\bon\s+the\s+other\s+hand\b", text_lower)
    similarity_markers = re.finditer(r"\bsimilarly\b|\blikewise\b|\bin\s+the\s+same\s+way\b", text_lower)

    contrast_positions = [m.start() for m in contrast_markers]
    similarity_positions = [m.start() for m in similarity_markers]

    for cp in contrast_positions:
        for sp in similarity_positions:
            if abs(cp - sp) < 500:  # Within ~5 lines
                # Find which line these are on
                for line_no, line in enumerate(document.lines, 1):
                    if "in contrast" in line.lower() and "similarly" in line.lower():
                        issues.append(
                            Issue(
                                id=f"logic.contradiction-mix-{line_no}",
                                category="logic",
                                rule_id="logic.contradictions",
                                severity=Severity.MEDIUM,
                                message="Mixed contrast and similarity markers near each other.",
                                recommendation="Choose one logical relationship: use contrast OR similarity markers, not both in the same argument.",
                                evidence=Evidence(
                                    line[:200], line_no, line_no, f"line {line_no}",
                                ),
                                confidence=55,
                                source="semantic-rule",
                            )
                        )
                        break
                break
        break  # Only flag once

    return issues


# ── Claim Without Evidence ─────────────────────────────────────────────────────

@rule(
    id="logic.claim-without-evidence",
    category="logic",
    name="Claim without evidence",
    description="Detects strong claims that lack citation or evidence support.",
    severity=Severity.MEDIUM,
    priority=22,
    source="semantic-rule",
)
def claim_without_evidence(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    max_claims = config.get("max_claims", 5)

    # Strong claim indicators
    claim_markers = [
        r"\bthis\s+(proves|demonstrates|shows|confirms|establishes|indicates)\b",
        r"\bthese\s+(results|findings|data|experiments)\s+(prove|demonstrate|show|confirm|establish)\b",
        r"\bit\s+(is|was)\s+(clear|obvious|evident|apparent)\s+that\b",
        r"\bwithout\s+(a\s+)?doubt\b",
        r"\b(there\s+is\s+)?no\s+(doubt|question|denying)\b",
        r"\bour\s+(results|approach|method|findings)\b",
        r"\b(significantly|dramatically|substantially)\b",
        r"\bthis\s+(paper|study|work|research)\s+(contributes|provides|offers)\b",
    ]
    claim_patterns = [re.compile(p, re.I) for p in claim_markers]

    # Evidence markers
    evidence_markers = [
        r"\[\d+\]",  # [1]
        r"\([A-Z][A-Za-z]+,\s*\d{4}\)",  # (Author, Year)
        r"\([A-Z][A-Za-z]+\s+et\s+al\.,\s*\d{4}\)",  # (Author et al., Year)
        r"\b(according\s+to|reported\s+by|shown\s+by|found\s+by)\b",
    ]
    evidence_pattern = re.compile("|".join(evidence_markers), re.I)

    for line_no, line in enumerate(document.lines, 1):
        if len(issues) >= max_claims:
            break

        # Check if line has a strong claim
        has_claim = any(p.search(line) for p in claim_patterns)
        if not has_claim:
            continue

        # Check if line has citation or evidence
        has_evidence = bool(evidence_pattern.search(line))

        if has_claim and not has_evidence:
            issues.append(
                Issue(
                    id=f"logic.claim-{line_no}",
                    category="logic",
                    rule_id="logic.claim-without-evidence",
                    severity=Severity.MEDIUM,
                    message=f"Strong claim on line {line_no} lacks supporting citation or evidence.",
                    recommendation="Support strong claims with a citation, data reference, or experimental evidence.",
                    evidence=Evidence(
                        line[:200], line_no, line_no, f"line {line_no}",
                    ),
                    confidence=65,
                    source="semantic-rule",
                )
            )

    return issues


# ── Conclusion Not Supported by Body ───────────────────────────────────────────

@rule(
    id="logic.unsupported-conclusion",
    category="logic",
    name="Unsupported conclusion",
    description="Checks if the conclusion references results/methods not discussed in the body.",
    severity=Severity.MEDIUM,
    priority=20,
    source="semantic-rule",
)
def unsupported_conclusion(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if len(document.lines) < 20:
        return issues

    # Find conclusion section
    conclusion_start: int | None = None
    body_end: int | None = None
    for i, line in enumerate(document.lines):
        if re.search(r"^(conclusion|summary|kết\s+luận)", line.strip(), re.I):
            conclusion_start = i
            break
        body_end = i

    if conclusion_start is None or body_end is None or body_end < 5:
        return issues

    body_text = " ".join(document.lines[:body_end]).lower()
    conclusion_lines = document.lines[conclusion_start:min(conclusion_start + 30, len(document.lines))]
    conclusion_text = " ".join(conclusion_lines).lower()

    # Extract key terms from conclusion
    conclusion_terms = re.findall(r"\b[A-Z][a-z]{2,}\b", conclusion_text)
    conclusion_terms = [t for t in conclusion_terms if len(t) > 3 and t.lower() not in {
        "this", "that", "with", "from", "have", "been", "more", "some", "than",
        "also", "such", "only", "just", "most", "each", "both", "these", "those",
        "their", "there", "which", "while", "after", "before", "other", "about",
        "however", "therefore", "results", "conclusion",
    }]

    # Check for terms in conclusion that were not in body
    unseen_terms = [t for t in conclusion_terms[:10] if t.lower() not in body_text]
    if unseen_terms:
        issues.append(
            Issue(
                id="logic.unsupported-conclusion-terms",
                category="logic",
                rule_id="logic.unsupported-conclusion",
                severity=Severity.MEDIUM,
                message=f"Conclusion introduces {len(unseen_terms)} term(s) not discussed in the main body.",
                recommendation="Ensure the conclusion only references concepts and results already presented in the body.",
                evidence=Evidence(
                    f"Terms not in body: {', '.join(unseen_terms[:5])}",
                    1, 1, "conclusion",
                ),
                confidence=70,
                source="semantic-rule",
            )
        )

    return issues


# ── Number / Date / Unit Consistency ───────────────────────────────────────────

@rule(
    id="logic.number-consistency",
    category="logic",
    name="Number/date/unit consistency",
    description="Detects inconsistent number formats, date formats, and unit usage.",
    severity=Severity.LOW,
    priority=15,
    source="syntax-rule",
)
def number_consistency_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []

    # Date format consistency
    date_formats = {
        "mm/dd/yyyy": re.findall(r"\b\d{2}/\d{2}/\d{4}\b", document.text),
        "dd/mm/yyyy": re.findall(r"\b\d{2}\.\d{2}\.\d{4}\b", document.text),
        "yyyy-mm-dd": re.findall(r"\b\d{4}-\d{2}-\d{2}\b", document.text),
        "Month DD, YYYY": re.findall(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}", document.text),
        "DD Month YYYY": re.findall(r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}", document.text),
    }

    active_formats = {fmt: count for fmt, count in date_formats.items() if count}
    if len(active_formats) > 1:
        formats_str = ", ".join(f"{fmt} ({len(dates)}x)" for fmt, dates in date_formats.items() if dates)
        issues.append(
            Issue(
                id="logic.inconsistent-date-formats",
                category="logic",
                rule_id="logic.number-consistency",
                severity=Severity.LOW,
                message=f"Inconsistent date formats: {formats_str}",
                recommendation="Use a single date format consistently throughout the document.",
                evidence=Evidence(
                    f"Multiple date formats found",
                    1, 1, "document",
                ),
                confidence=90,
                source="syntax-rule",
            )
        )

    # Number format consistency (words vs digits)
    word_numbers = re.findall(r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|twenty|thirty|forty|fifty|hundred|thousand)\b", document.text, re.I)
    digit_numbers = re.findall(r"\b\d+\b", document.text)

    # Only flag if both are used extensively in the same section
    if len(word_numbers) > 3 and len(digit_numbers) > 10:
        # Check if mixing happens in consecutive sentences
        for line_no, line in enumerate(document.lines, 1):
            has_word_num = bool(re.search(r"\b(?:five|ten|fifteen|twenty)", line, re.I))
            has_digit_num = bool(re.search(r"\b\d+\b", line))
            if has_word_num and has_digit_num:
                issues.append(
                    Issue(
                        id=f"logic.mixed-number-formats-{line_no}",
                        category="logic",
                        rule_id="logic.number-consistency",
                        severity=Severity.LOW,
                        message=f"Mixed word and digit number formats on line {line_no}.",
                        recommendation="Be consistent: use words for small numbers (one-nine) and digits for 10+.",
                        evidence=Evidence(
                            line[:200], line_no, line_no, f"line {line_no}",
                        ),
                        confidence=80,
                        source="syntax-rule",
                        autofix_allowed=True,
                    )
                )
                if len(issues) >= 3:
                    break

    return issues
