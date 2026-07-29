"""Compliance rules: ISO 9001, FDA, WHO, SOP validation, safety warnings, required signatures, versioning."""

from __future__ import annotations

import re
from typing import Any

from ..models import DocumentModel, Evidence, Issue, Severity
from ..profiles import Profile
from .registry import rule

# ── Patterns ──────────────────────────────────────────────────────────────────

DATE_PATTERN = re.compile(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}")
VERSION_PATTERN = re.compile(r"(?:version|v|rev(?:ision)?\.?)\s*(\d+(?:\.\d+)*)", re.I)
SIGNATURE_PATTERN = re.compile(
    r"(?:sign(?:ed|ature)?|approved\s+by|reviewed\s+by|authorized\s+by)", re.I
)
WARNING_KEYWORDS = {
    "warning", "caution", "danger", "attention", "important note",
    "cảnh báo", "chú ý", "nguy hiểm",
}
HAZARD_SYMBOLS = {"⚠", "☢", "☣", "⚡", "🔥", "🧪", "💀"}
SAFETY_KEYWORDS = {
    "safety", "protective", "ppe", "hazard", "risk", "emergency",
    "first aid", "evacuation", "an toàn", "nguy cơ",
}
REGULATORY_TERMS = {
    "comply", "compliance", "regulation", "regulatory", "standard",
    "requirement", "mandatory", "must", "shall", "tuân thủ",
}


# ── Safety Warning ────────────────────────────────────────────────────────────

@rule(
    id="compliance.safety-warning",
    category="compliance",
    name="Safety warning check",
    description="Checks for safety warnings in SOP and technical documents.",
    severity=Severity.HIGH,
    priority=50,
    source="semantic-rule",
)
def safety_warning_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    # Only check for profiles that need safety warnings
    if profile.id not in ("sop",):
        return issues

    text_lower = document.text.lower()

    # Check for warning keywords
    found_warnings = [kw for kw in WARNING_KEYWORDS if kw in text_lower]
    found_hazards = [sym for sym in HAZARD_SYMBOLS if sym in document.text]
    found_safety = [kw for kw in SAFETY_KEYWORDS if kw.lower() in text_lower]

    has_safety_section = any(
        "safety" in title.lower() or "warning" in title.lower()
        for _, title, _ in document.headings
    )

    # Score safety presence
    safety_score = len(found_warnings) + len(found_hazards) + (2 if has_safety_section else 0)

    if safety_score == 0:
        issues.append(
            Issue(
                id="compliance.no-safety-content",
                category="compliance",
                rule_id="compliance.safety-warning",
                severity=Severity.HIGH,
                message="No safety warnings or safety section detected in SOP document.",
                recommendation="Add a 'Safety' or 'Warnings' section with relevant hazard information, required PPE, and emergency procedures.",
                evidence=Evidence(
                    "No safety keywords found",
                    1, 1, "document",
                ),
                confidence=95,
                source="semantic-rule",
            )
        )
    elif safety_score < 3 and not has_safety_section:
        issues.append(
            Issue(
                id="compliance.insufficient-safety",
                category="compliance",
                rule_id="compliance.safety-warning",
                severity=Severity.MEDIUM,
                message=f"Insufficient safety content (score: {safety_score}). Add dedicated safety section.",
                recommendation="Create a dedicated 'Safety Warnings' section listing all hazards and precautions.",
                evidence=Evidence(
                    f"Safety score: {safety_score}",
                    1, 1, "document",
                ),
                confidence=80,
                source="semantic-rule",
            )
        )

    return issues


# ── Required Signatures / Approval ────────────────────────────────────────────

@rule(
    id="compliance.signatures",
    category="compliance",
    name="Required signatures check",
    description="Verifies SOP/compliance documents have signature or approval sections.",
    severity=Severity.HIGH,
    priority=40,
    source="syntax-rule",
)
def signatures_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if profile.id not in ("sop",):
        return issues

    text_lower = document.text.lower()

    # Check for signature-related content
    has_signatures = bool(SIGNATURE_PATTERN.search(text_lower))
    has_approval_heading = any(
        "approval" in title.lower()
        for _, title, _ in document.headings
    )
    has_date = bool(DATE_PATTERN.search(document.text))

    if not has_signatures and not has_approval_heading:
        issues.append(
            Issue(
                id="compliance.missing-signatures",
                category="compliance",
                rule_id="compliance.signatures",
                severity=Severity.HIGH,
                message="Missing approval/signature section for SOP document.",
                recommendation="Add an 'Approval' section with: Prepared by, Reviewed by, Approved by, and dates.",
                evidence=Evidence(
                    "No signature or approval content found",
                    1, 1, "document",
                ),
                confidence=95,
                source="syntax-rule",
            )
        )

    if not has_date:
        issues.append(
            Issue(
                id="compliance.missing-date",
                category="compliance",
                rule_id="compliance.signatures",
                severity=Severity.LOW,
                message="No dates found in the document.",
                recommendation="Add effective date, review date, and approval dates for compliance tracking.",
                evidence=Evidence(
                    "No dates detected",
                    1, 1, "document",
                ),
                confidence=85,
                source="syntax-rule",
            )
        )

    return issues


# ── Revision History ──────────────────────────────────────────────────────────

@rule(
    id="compliance.revision-history",
    category="compliance",
    name="Revision history check",
    description="Verifies SOP/documents have revision history section.",
    severity=Severity.MEDIUM,
    priority=35,
    source="syntax-rule",
)
def revision_history_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if profile.id != "sop":
        return issues

    text_lower = document.text.lower()
    heading_titles = [title.lower() for _, title, _ in document.headings]

    has_revision_heading = any(
        "revision" in t or "version" in t or "change log" in t or "document history" in t
        for t in heading_titles
    )

    has_version_marker = bool(VERSION_PATTERN.search(text_lower))

    if not has_revision_heading:
        severity = Severity.MEDIUM if has_version_marker else Severity.HIGH
        issues.append(
            Issue(
                id="compliance.missing-revision-history",
                category="compliance",
                rule_id="compliance.revision-history",
                severity=severity,
                message="Missing revision history section.",
                recommendation="Add a 'Revision History' table with: Version, Date, Description, Author.",
                evidence=Evidence(
                    "No revision history heading found",
                    1, 1, "document",
                ),
                confidence=95,
                source="syntax-rule",
            )
        )

    if not has_version_marker:
        issues.append(
            Issue(
                id="compliance.no-version-number",
                category="compliance",
                rule_id="compliance.revision-history",
                severity=Severity.MEDIUM,
                message="No version number found in document.",
                recommendation="Add a version number (e.g., 'Version 1.0') in the header or revision history.",
                evidence=Evidence(
                    "No version pattern detected",
                    1, 1, "document",
                ),
                confidence=90,
                source="syntax-rule",
            )
        )

    return issues


# ── ISO 9001 Compliance ───────────────────────────────────────────────────────

@rule(
    id="compliance.iso9001",
    category="compliance",
    name="ISO 9001 mandatory elements",
    description="Checks for ISO 9001 required documentation elements.",
    severity=Severity.HIGH,
    priority=45,
    source="cross-rule",
    pack_id="iso9001",
)
def iso9001_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    text_lower = document.text.lower()
    heading_titles = [title.lower() for _, title, _ in document.headings]

    # ISO 9001:2015 required documented information
    iso_requirements = [
        ("quality policy", "Quality Policy", Severity.HIGH),
        ("quality objectives", "Quality Objectives", Severity.HIGH),
        ("scope", "Scope of QMS", Severity.HIGH),
    ]

    for keyword, display, severity in iso_requirements:
        found = keyword in text_lower or any(keyword in t for t in heading_titles)
        if not found:
            issues.append(
                Issue(
                    id=f"compliance.iso-missing-{keyword.replace(' ', '-')}",
                    category="compliance",
                    rule_id="compliance.iso9001",
                    severity=severity,
                    message=f"Missing ISO 9001 required element: '{display}'.",
                    recommendation=f"Add documentation for '{display}' as required by ISO 9001:2015 clause 7.5.",
                    evidence=Evidence(
                        f"ISO 9001 element '{display}' not found",
                        1, 1, "document",
                    ),
                    confidence=90,
                    source="cross-rule",
                )
            )

    # Check for document control
    doc_control_keywords = [
        "document control", "document management", "document approval",
        "document review", "document update",
    ]
    has_doc_control = any(kw in text_lower for kw in doc_control_keywords)

    if not has_doc_control:
        issues.append(
            Issue(
                id="compliance.iso-doc-control",
                category="compliance",
                rule_id="compliance.iso9001",
                severity=Severity.MEDIUM,
                message="Missing document control procedures (ISO 9001 clause 7.5.3).",
                recommendation="Add a section describing document approval, review, update, and version control procedures.",
                evidence=Evidence(
                    "No document control terms found",
                    1, 1, "document",
                ),
                confidence=85,
                source="cross-rule",
            )
        )

    return issues


# ── FDA Compliance ────────────────────────────────────────────────────────────

@rule(
    id="compliance.fda",
    category="compliance",
    name="FDA 21 CFR Part 11 compliance",
    description="Checks for FDA electronic records/signatures compliance elements.",
    severity=Severity.HIGH,
    priority=45,
    source="cross-rule",
    pack_id="fda",
)
def fda_compliance_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    text_lower = document.text.lower()

    # 21 CFR Part 11 key elements
    fda_elements = [
        ("audit trail", "Audit Trail"),
        ("electronic signature", "Electronic Signature"),
        ("user identification", "User Identification"),
        ("system validation", "System Validation"),
        ("data integrity", "Data Integrity"),
        ("record retention", "Record Retention"),
        ("access control", "Access Control"),
    ]

    found_elements = 0
    for keyword, display in fda_elements:
        if keyword in text_lower:
            found_elements += 1

    # GxP / validation
    gxp_terms = ["gmp", "glp", "gcp", "gxp", "validation", "qualification"]
    has_gxp = any(t in text_lower for t in gxp_terms)

    if not has_gxp:
        issues.append(
            Issue(
                id="compliance.fda-gxp",
                category="compliance",
                rule_id="compliance.fda",
                severity=Severity.HIGH,
                message="No GxP/validation terms found (FDA-regulated documents).",
                recommendation="Include validation and GxP compliance documentation as per 21 CFR Part 820.",
                evidence=Evidence(
                    "No GxP terms detected",
                    1, 1, "document",
                ),
                confidence=85,
                source="cross-rule",
            )
        )

    if found_elements < 3:
        issues.append(
            Issue(
                id="compliance.fda-part11",
                category="compliance",
                rule_id="compliance.fda",
                severity=Severity.HIGH,
                message=f"Insufficient 21 CFR Part 11 elements (found {found_elements}/7).",
                recommendation=f"Add documentation for: audit trail, electronic signature, data integrity, access control.",
                evidence=Evidence(
                    f"Found {found_elements}/7 FDA Part 11 elements",
                    1, 1, "document",
                ),
                confidence=80,
                source="cross-rule",
            )
        )

    return issues


# ── WHO Compliance ────────────────────────────────────────────────────────────

@rule(
    id="compliance.who",
    category="compliance",
    name="WHO guidelines compliance",
    description="Checks for WHO documentation requirements.",
    severity=Severity.HIGH,
    priority=40,
    source="cross-rule",
    pack_id="who",
)
def who_compliance_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    text_lower = document.text.lower()

    who_elements = [
        ("objective", "Objective/Purpose"),
        ("scope", "Scope"),
        ("responsibility", "Responsibility"),
        ("procedure", "Procedure"),
        ("documentation", "Documentation/Records"),
        ("reference", "References"),
        ("annex", "Annex/Appendix"),
    ]

    found_elements = 0
    for keyword, display in who_elements:
        if keyword in text_lower:
            found_elements += 1

    if found_elements < 4:
        issues.append(
            Issue(
                id="compliance.who-structure",
                category="compliance",
                rule_id="compliance.who",
                severity=Severity.MEDIUM,
                message=f"Document may not follow WHO structure guidelines (found {found_elements}/{len(who_elements)} elements).",
                recommendation="Follow WHO document structure: Objective, Scope, Responsibility, Procedure, Documentation, References.",
                evidence=Evidence(
                    f"Found {found_elements}/7 WHO-expected sections",
                    1, 1, "document",
                ),
                confidence=75,
                source="cross-rule",
            )
        )

    return issues


# ── SOP Validation ────────────────────────────────────────────────────────────

@rule(
    id="compliance.sop-validation",
    category="compliance",
    name="SOP document validation",
    description="Comprehensive SOP quality checks.",
    severity=Severity.HIGH,
    priority=50,
    source="cross-rule",
    pack_id="sop",
)
def sop_validation_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if profile.id != "sop":
        return issues

    text_lower = document.text.lower()
    sections = {title.lower() for _, title, _ in document.headings}

    # SOP must use imperative/active language
    imperative_markers = ["must", "shall", "should", "will", "ensure", "verify", "check"]
    has_imperative = any(m in text_lower for m in imperative_markers)

    if not has_imperative:
        issues.append(
            Issue(
                id="compliance.sop-no-imperative",
                category="compliance",
                rule_id="compliance.sop-validation",
                severity=Severity.HIGH,
                message="SOP lacks imperative/obligation language (must, shall, ensure).",
                recommendation="Use 'must' and 'shall' to define mandatory actions in procedures.",
                evidence=Evidence(
                    "No obligation language detected",
                    1, 1, "document",
                ),
                confidence=90,
                source="cross-rule",
            )
        )

    # Check for numbered steps
    step_pattern = re.compile(r"(?:^\s*\d+[.)]\s+|^\s*Step\s+\d+)", re.M)
    has_numbered_steps = bool(step_pattern.search(document.text))

    if not has_numbered_steps:
        issues.append(
            Issue(
                id="compliance.sop-no-steps",
                category="compliance",
                rule_id="compliance.sop-validation",
                severity=Severity.MEDIUM,
                message="SOP procedure does not use numbered steps.",
                recommendation="Break down procedures into clear, numbered sequential steps.",
                evidence=Evidence(
                    "No numbered steps detected",
                    1, 1, "document",
                ),
                confidence=85,
                source="semantic-rule",
            )
        )

    # Regulatory terms usage
    regulatory_count = sum(1 for t in REGULATORY_TERMS if t in text_lower)
    if regulatory_count < 3:
        issues.append(
            Issue(
                id="compliance.sop-regulatory",
                category="compliance",
                rule_id="compliance.sop-validation",
                severity=Severity.MEDIUM,
                message="Insufficient regulatory/compliance language in SOP (found {regulatory_count} terms).",
                recommendation="Include compliance terms: 'shall', 'must', 'comply', 'requirement', 'standard'.",
                evidence=Evidence(
                    f"Found {regulatory_count} regulatory terms",
                    1, 1, "document",
                ),
                confidence=75,
                source="semantic-rule",
            )
        )

    return issues


# ── Versioning ────────────────────────────────────────────────────────────────

@rule(
    id="compliance.versioning",
    category="compliance",
    name="Document versioning check",
    description="Checks for proper version numbering and document identification.",
    severity=Severity.MEDIUM,
    priority=25,
    source="syntax-rule",
)
def versioning_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if profile.id not in ("sop",):
        return issues

    text_lower = document.text.lower()
    versions = VERSION_PATTERN.findall(text_lower)

    if not versions:
        issues.append(
            Issue(
                id="compliance.no-versioning",
                category="compliance",
                rule_id="compliance.versioning",
                severity=Severity.MEDIUM,
                message="No version numbering found in document.",
                recommendation="Add version number (e.g., 'Version 1.0') and include in revision history.",
                evidence=Evidence(
                    "No version number detected",
                    1, 1, "document",
                ),
                confidence=95,
                source="syntax-rule",
            )
        )
    else:
        # Check for major version 0 (draft)
        for v in versions:
            if v.startswith("0."):
                issues.append(
                    Issue(
                        id="compliance.draft-version",
                        category="compliance",
                        rule_id="compliance.versioning",
                        severity=Severity.LOW,
                        message=f"Document is version {v} (draft).",
                        recommendation="Promote to Version 1.0 when finalized.",
                        evidence=Evidence(
                            f"Version {v} detected",
                            1, 1, "document",
                        ),
                        confidence=90,
                        source="syntax-rule",
                    )
                )

    return issues


# ── Mandatory Compliance Sections ─────────────────────────────────────────────

@rule(
    id="compliance.mandatory-sections",
    category="compliance",
    name="Mandatory compliance sections",
    description="Checks for sections mandated by the active compliance pack.",
    severity=Severity.HIGH,
    priority=40,
    source="cross-rule",
)
def mandatory_sections_check(document: DocumentModel, profile: Profile, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    pack_id = config.get("pack_id", "")

    # Section requirements by pack
    pack_sections: dict[str, list[tuple[str, str, Severity]]] = {
        "iso9001": [
            ("quality policy", "Quality Policy", Severity.HIGH),
            ("objectives", "Quality Objectives", Severity.HIGH),
            ("scope", "Scope", Severity.HIGH),
        ],
        "fda": [
            ("validation", "System Validation", Severity.HIGH),
            ("audit trail", "Audit Trail", Severity.HIGH),
            ("change control", "Change Control", Severity.HIGH),
        ],
        "who": [
            ("objective", "Objective", Severity.HIGH),
            ("procedure", "Procedure", Severity.HIGH),
            ("documentation", "Documentation", Severity.MEDIUM),
        ],
    }

    if pack_id not in pack_sections:
        return issues

    text_lower = document.text.lower()
    for keyword, display, severity in pack_sections[pack_id]:
        if keyword not in text_lower:
            issues.append(
                Issue(
                    id=f"compliance.mandatory-{pack_id}-{keyword.replace(' ', '-')}",
                    category="compliance",
                    rule_id="compliance.mandatory-sections",
                    severity=severity,
                    message=f"Missing mandatory section '{display}' required by {pack_id.upper()} pack.",
                    recommendation=f"Add a '{display}' section as required by {pack_id.upper()} compliance standards.",
                    evidence=Evidence(
                        f"'{display}' not found in document",
                        1, 1, "document",
                    ),
                    confidence=95,
                    source="cross-rule",
                )
            )

    return issues
