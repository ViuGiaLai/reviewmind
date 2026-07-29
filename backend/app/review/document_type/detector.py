"""Document Type Detection — implements PDS Chapter 4.

Rule-first approach: keyword signals are scored and the highest-scoring
type wins.  A secondary pass maps the winning type to a profile_id so the
rest of the pipeline can load the correct review profile without any extra
logic.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ─── Document Types ────────────────────────────────────────────────────────────

class DocumentType(str, Enum):
    # Academic
    THESIS = "thesis"
    DISSERTATION = "dissertation"
    JOURNAL_ARTICLE = "journal_article"
    CONFERENCE_PAPER = "conference_paper"
    LITERATURE_REVIEW = "literature_review"
    RESEARCH_PROPOSAL = "research_proposal"
    INTERNSHIP_REPORT = "internship_report"
    SURVEY_PAPER = "survey_paper"
    LAB_REPORT = "lab_report"

    # Technical
    SOFTWARE_ARCHITECTURE = "software_architecture"
    SYSTEM_DESIGN = "system_design"
    API_SPECIFICATION = "api_specification"
    TECHNICAL_SPEC = "technical_spec"
    USER_MANUAL = "user_manual"
    DEVELOPER_GUIDE = "developer_guide"
    RELEASE_NOTE = "release_note"
    RFC = "rfc"

    # Business
    PROPOSAL = "proposal"
    BUSINESS_REPORT = "business_report"
    FINANCIAL_REPORT = "financial_report"
    MEETING_MINUTES = "meeting_minutes"
    PROJECT_PLAN = "project_plan"

    # SOP / Compliance
    SOP = "sop"
    POLICY = "policy"
    ISO_DOCUMENT = "iso_document"
    PROCESS_DOCUMENT = "process_document"

    # General
    REPORT = "report"
    ESSAY = "essay"
    UNKNOWN = "unknown"


# ─── Detection Result ──────────────────────────────────────────────────────────

@dataclass
class DetectionResult:
    """The outcome of document-type detection."""
    document_type: DocumentType
    profile_id: str
    confidence: float  # 0.0 – 1.0
    signals: list[str] = field(default_factory=list)
    alternative_types: list[tuple[DocumentType, float]] = field(default_factory=list)


# ─── Profile mapping ───────────────────────────────────────────────────────────

_ACADEMIC_TYPES = {
    DocumentType.THESIS,
    DocumentType.DISSERTATION,
    DocumentType.JOURNAL_ARTICLE,
    DocumentType.CONFERENCE_PAPER,
    DocumentType.LITERATURE_REVIEW,
    DocumentType.RESEARCH_PROPOSAL,
    DocumentType.INTERNSHIP_REPORT,
    DocumentType.SURVEY_PAPER,
    DocumentType.LAB_REPORT,
}

_TECHNICAL_TYPES = {
    DocumentType.SOFTWARE_ARCHITECTURE,
    DocumentType.SYSTEM_DESIGN,
    DocumentType.API_SPECIFICATION,
    DocumentType.TECHNICAL_SPEC,
    DocumentType.USER_MANUAL,
    DocumentType.DEVELOPER_GUIDE,
    DocumentType.RELEASE_NOTE,
    DocumentType.RFC,
}

_SOP_TYPES = {
    DocumentType.SOP,
    DocumentType.POLICY,
    DocumentType.ISO_DOCUMENT,
    DocumentType.PROCESS_DOCUMENT,
}

_BUSINESS_TYPES = {
    DocumentType.PROPOSAL,
    DocumentType.BUSINESS_REPORT,
    DocumentType.FINANCIAL_REPORT,
    DocumentType.MEETING_MINUTES,
    DocumentType.PROJECT_PLAN,
}


def _type_to_profile(doc_type: DocumentType) -> str:
    if doc_type in _ACADEMIC_TYPES:
        return "academic"
    if doc_type in _TECHNICAL_TYPES:
        return "technical_design"
    if doc_type in _SOP_TYPES:
        return "sop"
    if doc_type in _BUSINESS_TYPES:
        return "business"
    return "general"


# ─── Detector ─────────────────────────────────────────────────────────────────

class DocumentTypeDetector:
    """Detect the type of a document from its structure and content.

    Usage::

        detector = DocumentTypeDetector()
        result = detector.detect(
            headings=["Abstract", "Introduction", "Methodology", "Results", "References"],
            text=full_text,
            filename="paper.pdf",
        )
        print(result.document_type, result.profile_id, result.confidence)
    """

    # ── filename keyword maps ──────────────────────────────────────────────────
    #   Each entry: (regex pattern, DocumentType, confidence_boost, signal_label)
    _FILENAME_RULES: list[tuple[str, DocumentType, float, str]] = [
        # Vietnamese
        (r"lu[aậ]n\s*v[aă]n", DocumentType.THESIS, 0.90, "filename contains 'luận văn' (Vietnamese thesis)"),
        (r"kh[oó]a\s*lu[aậ]n", DocumentType.THESIS, 0.90, "filename contains 'khóa luận' (Vietnamese thesis)"),
        (r"đ[oồ]\s*[aá]n", DocumentType.THESIS, 0.85, "filename contains 'đồ án' (Vietnamese capstone)"),
        (r"b[aá]o\s*c[aá]o\s*th[uự]c\s*t[aậ]p", DocumentType.INTERNSHIP_REPORT, 0.90,
         "filename contains 'báo cáo thực tập' (Vietnamese internship report)"),
        (r"quy\s*tr[iì]nh", DocumentType.SOP, 0.85, "filename contains 'quy trình' (Vietnamese procedure)"),
        (r"h[uướ][oơ]ng\s*d[aẫ]n", DocumentType.SOP, 0.80, "filename contains 'hướng dẫn' (Vietnamese guideline)"),
        (r"thi[eế]t\s*k[eế]\s*h[eệ]\s*th[oố]ng", DocumentType.SYSTEM_DESIGN, 0.90,
         "filename contains 'thiết kế hệ thống' (Vietnamese system design)"),
        (r"ki[eế]n\s*tr[uú]c", DocumentType.SOFTWARE_ARCHITECTURE, 0.88,
         "filename contains 'kiến trúc' (Vietnamese architecture)"),

        # English
        (r"\bthesis\b", DocumentType.THESIS, 0.90, "filename contains 'thesis'"),
        (r"\bdissertation\b", DocumentType.DISSERTATION, 0.90, "filename contains 'dissertation'"),
        (r"\bsop\b", DocumentType.SOP, 0.90, "filename contains 'SOP'"),
        (r"\bprocedure\b", DocumentType.SOP, 0.80, "filename contains 'procedure'"),
        (r"\barchitecture\b", DocumentType.SOFTWARE_ARCHITECTURE, 0.85, "filename contains 'architecture'"),
        (r"\bdesign\b", DocumentType.SYSTEM_DESIGN, 0.75, "filename contains 'design'"),
        (r"\bspec(ification)?\b", DocumentType.TECHNICAL_SPEC, 0.80, "filename contains 'spec'"),
        (r"\bapi\b", DocumentType.API_SPECIFICATION, 0.85, "filename contains 'api'"),
        (r"\brfc\b", DocumentType.RFC, 0.90, "filename contains 'rfc'"),
        (r"\brelease.?note", DocumentType.RELEASE_NOTE, 0.88, "filename contains 'release note'"),
        (r"\bmanual\b", DocumentType.USER_MANUAL, 0.85, "filename contains 'manual'"),
        (r"\bguide\b", DocumentType.DEVELOPER_GUIDE, 0.78, "filename contains 'guide'"),
        (r"\bproposal\b", DocumentType.PROPOSAL, 0.82, "filename contains 'proposal'"),
        (r"\bminutes\b", DocumentType.MEETING_MINUTES, 0.90, "filename contains 'minutes'"),
        (r"\bfinancial\b", DocumentType.FINANCIAL_REPORT, 0.85, "filename contains 'financial'"),
        (r"\bproject.?plan\b", DocumentType.PROJECT_PLAN, 0.88, "filename contains 'project plan'"),
        (r"\bpolicy\b", DocumentType.POLICY, 0.85, "filename contains 'policy'"),
        (r"\biso\b", DocumentType.ISO_DOCUMENT, 0.82, "filename contains 'iso'"),
        (r"\blab.?report\b", DocumentType.LAB_REPORT, 0.88, "filename contains 'lab report'"),
    ]

    # ── heading / section signal sets ─────────────────────────────────────────
    # Format: (frozenset of normalised keywords that must ALL be present,
    #          DocumentType, confidence, signal_label)
    _HEADING_COMBOS: list[tuple[frozenset[str], DocumentType, float, str]] = [
        # Strong academic signals
        (
            frozenset({"abstract", "introduction", "methodology", "results", "references"}),
            DocumentType.JOURNAL_ARTICLE, 0.95,
            "headings: Abstract + Introduction + Methodology + Results + References → journal article",
        ),
        (
            frozenset({"abstract", "introduction", "conclusion", "references"}),
            DocumentType.JOURNAL_ARTICLE, 0.80,
            "headings: Abstract + Introduction + Conclusion + References → journal article",
        ),
        (
            frozenset({"abstract", "conclusion", "references"}),
            DocumentType.THESIS, 0.70,
            "headings: Abstract + Conclusion + References → thesis candidate",
        ),
        (
            frozenset({"literature review", "methodology", "references"}),
            DocumentType.THESIS, 0.78,
            "headings: Literature Review + Methodology + References → thesis",
        ),
        (
            frozenset({"abstract", "introduction", "survey", "references"}),
            DocumentType.SURVEY_PAPER, 0.82,
            "headings: Abstract + Introduction + Survey + References → survey paper",
        ),
        (
            frozenset({"objective", "materials", "methods", "results"}),
            DocumentType.LAB_REPORT, 0.88,
            "headings: Objective + Materials + Methods + Results → lab report",
        ),
        # Technical
        (
            frozenset({"system overview", "components", "api", "deployment"}),
            DocumentType.SOFTWARE_ARCHITECTURE, 0.92,
            "headings: System Overview + Components + API + Deployment → software architecture",
        ),
        (
            frozenset({"architecture", "components", "deployment"}),
            DocumentType.SOFTWARE_ARCHITECTURE, 0.85,
            "headings: Architecture + Components + Deployment → software architecture",
        ),
        (
            frozenset({"system design", "database", "api"}),
            DocumentType.SYSTEM_DESIGN, 0.85,
            "headings: System Design + Database + API → system design",
        ),
        (
            frozenset({"endpoints", "request", "response", "authentication"}),
            DocumentType.API_SPECIFICATION, 0.90,
            "headings: Endpoints + Request + Response + Authentication → API spec",
        ),
        (
            frozenset({"changelog", "version", "release"}),
            DocumentType.RELEASE_NOTE, 0.88,
            "headings: Changelog + Version + Release → release note",
        ),
        # SOP / Compliance
        (
            frozenset({"purpose", "scope", "procedure"}),
            DocumentType.SOP, 0.90,
            "headings: Purpose + Scope + Procedure → SOP",
        ),
        (
            frozenset({"purpose", "scope", "responsibility", "procedure"}),
            DocumentType.SOP, 0.95,
            "headings: Purpose + Scope + Responsibility + Procedure → SOP",
        ),
        (
            frozenset({"purpose", "scope", "policy", "compliance"}),
            DocumentType.POLICY, 0.88,
            "headings: Purpose + Scope + Policy + Compliance → policy document",
        ),
        # Business
        (
            frozenset({"executive summary", "background", "objectives"}),
            DocumentType.BUSINESS_REPORT, 0.82,
            "headings: Executive Summary + Background + Objectives → business report",
        ),
        (
            frozenset({"executive summary", "scope", "budget"}),
            DocumentType.PROPOSAL, 0.88,
            "headings: Executive Summary + Scope + Budget → proposal",
        ),
        (
            frozenset({"attendees", "agenda", "action items"}),
            DocumentType.MEETING_MINUTES, 0.95,
            "headings: Attendees + Agenda + Action Items → meeting minutes",
        ),
        (
            frozenset({"milestones", "timeline", "deliverables", "risks"}),
            DocumentType.PROJECT_PLAN, 0.90,
            "headings: Milestones + Timeline + Deliverables + Risks → project plan",
        ),
        (
            frozenset({"income", "expenses", "balance sheet"}),
            DocumentType.FINANCIAL_REPORT, 0.92,
            "headings: Income + Expenses + Balance Sheet → financial report",
        ),
    ]

    # ── full-text keyword signals ──────────────────────────────────────────────
    # Format: (list of keywords where ANY match scores,
    #          DocumentType, per-match confidence increment, label)
    _TEXT_SIGNALS: list[tuple[list[str], DocumentType, float, str]] = [
        # Academic
        (["abstract", "introduction", "methodology", "references"],
         DocumentType.JOURNAL_ARTICLE, 0.10, "text: academic structural keywords"),
        (["thesis", "dissertation", "graduate", "faculty", "supervisor"],
         DocumentType.THESIS, 0.12, "text: thesis/dissertation keywords"),
        (["internship", "thực tập", "intern report"],
         DocumentType.INTERNSHIP_REPORT, 0.15, "text: internship report keywords"),
        (["literature review", "systematic review", "bibliometric"],
         DocumentType.LITERATURE_REVIEW, 0.18, "text: literature review keywords"),
        (["research proposal", "research questions", "proposed methodology"],
         DocumentType.RESEARCH_PROPOSAL, 0.18, "text: research proposal keywords"),
        (["survey", "questionnaire", "respondents", "sample size"],
         DocumentType.SURVEY_PAPER, 0.12, "text: survey paper keywords"),
        # Technical
        (["microservice", "docker", "kubernetes", "ci/cd", "devops"],
         DocumentType.SOFTWARE_ARCHITECTURE, 0.12, "text: DevOps/cloud architecture keywords"),
        (["api endpoint", "rest api", "graphql", "swagger", "openapi"],
         DocumentType.API_SPECIFICATION, 0.15, "text: API specification keywords"),
        (["release notes", "bug fix", "known issues", "changelog"],
         DocumentType.RELEASE_NOTE, 0.15, "text: release note keywords"),
        (["rfc ", "request for comments", "ietf"],
         DocumentType.RFC, 0.18, "text: RFC keywords"),
        (["iso 9001", "iso 27001", "iso/iec", "certification"],
         DocumentType.ISO_DOCUMENT, 0.18, "text: ISO document keywords"),
        # Business
        (["executive summary", "market analysis", "competitive landscape"],
         DocumentType.BUSINESS_REPORT, 0.12, "text: business report keywords"),
        (["return on investment", "roi", "profit", "revenue", "financial statement"],
         DocumentType.FINANCIAL_REPORT, 0.12, "text: financial report keywords"),
        (["action items", "attendees", "minutes of meeting", "mom"],
         DocumentType.MEETING_MINUTES, 0.15, "text: meeting minutes keywords"),
        # SOP / Process
        (["step 1", "step 2", "step 3", "procedure", "work instruction"],
         DocumentType.SOP, 0.10, "text: procedural step keywords"),
        (["revision history", "document control", "approved by", "effective date"],
         DocumentType.SOP, 0.12, "text: document-control keywords"),
        # Vietnamese SOP
        (["bước 1", "bước 2", "quy trình", "hướng dẫn thực hiện"],
         DocumentType.SOP, 0.12, "text: Vietnamese SOP keywords"),
        # Vietnamese Academic
        (["luận văn", "khóa luận", "đồ án", "giảng viên hướng dẫn"],
         DocumentType.THESIS, 0.15, "text: Vietnamese thesis keywords"),
        (["báo cáo thực tập", "đơn vị thực tập", "nhận xét của đơn vị"],
         DocumentType.INTERNSHIP_REPORT, 0.18, "text: Vietnamese internship report keywords"),
    ]

    # ─── Title / first-page heuristics ────────────────────────────────────────
    _TITLE_PATTERNS: list[tuple[str, DocumentType, float, str]] = [
        (r"\bthesis\b|\bdissertation\b", DocumentType.THESIS, 0.20,
         "title contains thesis/dissertation"),
        (r"lu[aậ]n\s*v[aă]n|kh[oó]a\s*lu[aậ]n|đ[oồ]\s*[aá]n", DocumentType.THESIS, 0.20,
         "title contains Vietnamese thesis keywords"),
        (r"b[aá]o\s*c[aá]o\s*th[uự]c\s*t[aậ]p", DocumentType.INTERNSHIP_REPORT, 0.20,
         "title: báo cáo thực tập"),
        (r"\bsoftware\s+architecture\b|\bsystem\s+design\b", DocumentType.SOFTWARE_ARCHITECTURE, 0.18,
         "title: software architecture / system design"),
        (r"\bapi\s+(spec|guide|reference)\b", DocumentType.API_SPECIFICATION, 0.20,
         "title: API spec/guide/reference"),
        (r"\bsop\b|\bstandard\s+operating\s+procedure\b", DocumentType.SOP, 0.20,
         "title: SOP / standard operating procedure"),
    ]

    # ─────────────────────────────────────────────────────────────────────────

    def detect(
        self,
        headings: list[str] | None = None,
        text: str = "",
        filename: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> DetectionResult:
        """Detect document type from structure, content, and filename.

        Parameters
        ----------
        headings:
            List of heading strings extracted from the document (any level).
        text:
            Full plain-text content of the document.
        filename:
            Original filename (used as a strong prior signal).
        metadata:
            Optional dict with extra metadata (e.g. ``title`` key for doc title).

        Returns
        -------
        DetectionResult
        """
        headings = headings or []
        metadata = metadata or {}
        scores: dict[DocumentType, float] = {}
        signals: list[str] = []

        text_lower = text.casefold()
        filename_lower = filename.casefold()
        title: str = metadata.get("title", "").casefold()

        # ── 1. Filename rules ────────────────────────────────────────────────
        for pattern, doc_type, boost, label in self._FILENAME_RULES:
            if re.search(pattern, filename_lower, re.IGNORECASE):
                scores[doc_type] = max(scores.get(doc_type, 0.0), boost)
                signals.append(f"[filename] {label}")

        # ── 2. Metadata title rules ─────────────────────────────────────────
        if title:
            for pattern, doc_type, boost, label in self._TITLE_PATTERNS:
                if re.search(pattern, title, re.IGNORECASE):
                    prev = scores.get(doc_type, 0.0)
                    scores[doc_type] = min(1.0, prev + boost)
                    signals.append(f"[title] {label}")

        # ── 3. Heading combination rules ────────────────────────────────────
        normalised_headings: set[str] = {h.strip().casefold() for h in headings}
        for required_set, doc_type, confidence, label in self._HEADING_COMBOS:
            # Check if every keyword in required_set appears in at least one heading
            if all(
                any(kw in heading for heading in normalised_headings)
                for kw in required_set
            ):
                prev = scores.get(doc_type, 0.0)
                scores[doc_type] = max(prev, confidence)
                signals.append(f"[headings] {label}")

        # ── 4. Full-text keyword signals ────────────────────────────────────
        for keywords, doc_type, increment, label in self._TEXT_SIGNALS:
            matched_count = sum(1 for kw in keywords if kw in text_lower)
            if matched_count > 0:
                contribution = increment * matched_count
                scores[doc_type] = min(1.0, scores.get(doc_type, 0.0) + contribution)
                signals.append(f"[text] {label} ({matched_count}/{len(keywords)} matched)")

        # ── 5. Thesis title special case (heading + thesis keyword in title) ─
        if title and re.search(r"thesis|dissertation|lu[aậ]n\s*v[aă]n", title, re.IGNORECASE):
            thesis_headings = {"abstract", "conclusion", "references"}
            if any(kw in normalised_headings for kw in thesis_headings):
                prev = scores.get(DocumentType.THESIS, 0.0)
                scores[DocumentType.THESIS] = min(1.0, prev + 0.15)
                signals.append("[title+headings] thesis keyword in title + academic headings found")

        # ── 6. Determine winner ─────────────────────────────────────────────
        if not scores:
            best_type = DocumentType.UNKNOWN
            best_confidence = 0.0
        else:
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            best_type, best_confidence = sorted_scores[0]
            alternatives = [(t, c) for t, c in sorted_scores[1:] if c >= 0.30][:3]

        profile_id = _type_to_profile(best_type)

        return DetectionResult(
            document_type=best_type,
            profile_id=profile_id,
            confidence=round(min(best_confidence, 1.0), 4),
            signals=signals,
            alternative_types=alternatives if scores else [],
        )
