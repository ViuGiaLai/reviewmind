from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeAlias
from uuid import uuid4

JSONDict: TypeAlias = dict[str, Any]

__all__ = [
    "Severity",
    "BlockType",
    "StableNodeID",
    "SourceLocation",
    "TextOffsetMapping",
    "Hyperlink",
    "Citation",
    "TableCell",
    "TableData",
    "FigureData",
    "EquationData",
    "Sentence",
    "DocumentBlock",
    "DocumentMetadata",
    "EvidenceRange",
    "Evidence",
    "DocumentModel",
    "Issue",
    "ReviewRequest",
    "ReviewResult",
]


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ─── Rich Block Types ──────────────────────────────────────────────────────────

class BlockType(str, Enum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    LIST_ITEM = "list_item"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    ENDNOTE = "endnote"
    HEADER = "header"
    FOOTER = "footer"
    EQUATION = "equation"
    CODE_BLOCK = "code_block"
    PAGE_BREAK = "page_break"
    SENTENCE = "sentence"
    HYPERLINK = "hyperlink"
    CITATION = "citation"


@dataclass(slots=True, frozen=True)
class StableNodeID:
    """Stable identifier for any node in the document model."""
    id: str = field(default_factory=lambda: str(uuid4()))
    node_type: str = "block"  # block, table_cell, figure, sentence, heading
    block_index: int = -1
    parent_id: str = ""


@dataclass(slots=True, frozen=True)
class SourceLocation:
    """Precise source location in the original document."""
    # Page / PDF coordinates
    page_number: int = 0
    page_label: str = ""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0

    # Line-based (text / DOCX)
    line_start: int = 0
    line_end: int = 0
    char_start: int = 0
    char_end: int = 0

    # DOCX specific
    paragraph_id: int = 0
    table_id: int = -1
    row_id: int = -1
    col_id: int = -1

    # PDF specific
    page_bbox: tuple[float, float, float, float] = (0, 0, 0, 0)  # (x0, y0, x1, y1)

    # Stable node reference
    node_id: str = ""


@dataclass(slots=True, frozen=True)
class TextOffsetMapping:
    """Maps between normalized text positions and original source positions."""
    normalized_start: int  # char offset in normalized text
    normalized_end: int
    original_start: int    # char offset in original document
    original_end: int
    source_location: SourceLocation | None = None


@dataclass(slots=True, frozen=True)
class Hyperlink:
    """A hyperlink in the document."""
    text: str
    url: str
    tooltip: str = ""
    location: SourceLocation = field(default_factory=SourceLocation)
    node_id: str = ""


@dataclass(slots=True, frozen=True)
class Citation:
    """A citation or reference in the document."""
    raw_text: str
    citation_type: str = ""  # "inline", "footnote", "endnote", "biblio"
    author: str = ""
    year: str = ""
    title: str = ""
    doi: str = ""
    location: SourceLocation = field(default_factory=SourceLocation)
    node_id: str = ""


@dataclass(slots=True, frozen=True)
class TableCell:
    text: str
    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1
    bold: bool = False
    italic: bool = False
    alignment: str = "left"
    location: SourceLocation = field(default_factory=SourceLocation)
    node_id: str = ""


@dataclass(slots=True, frozen=True)
class TableData:
    rows: int
    cols: int
    cells: list[TableCell]
    caption: str = ""
    location: SourceLocation = field(default_factory=SourceLocation)
    node_id: str = ""


@dataclass(slots=True, frozen=True)
class FigureData:
    alt_text: str = ""
    caption: str = ""
    image_path: str = ""
    image_data: bytes | None = None
    width: float = 0.0
    height: float = 0.0
    location: SourceLocation = field(default_factory=SourceLocation)
    node_id: str = ""


@dataclass(slots=True, frozen=True)
class EquationData:
    latex: str = ""
    plain_text: str = ""
    mathml: str = ""
    location: SourceLocation = field(default_factory=SourceLocation)
    node_id: str = ""


@dataclass(slots=True, frozen=True)
class Sentence:
    """A sentence within a document block."""
    text: str
    index: int  # Position within parent block
    start_char: int  # Char offset within parent block text
    end_char: int
    location: SourceLocation = field(default_factory=SourceLocation)
    node_id: str = ""
    block_id: str = ""  # Reference to parent block node_id


@dataclass(slots=True, frozen=True)
class DocumentBlock:
    """A single block of content in the document."""
    type: BlockType
    text: str
    level: int = 0  # Heading level, list nesting, etc.
    node_id: str = field(default_factory=lambda: str(uuid4()))
    location: SourceLocation = field(default_factory=SourceLocation)

    # Rich content
    table: TableData | None = None
    figure: FigureData | None = None
    equation: EquationData | None = None

    # Sentences
    sentences: list[Sentence] = field(default_factory=list)

    # Hyperlinks / Citations within this block
    hyperlinks: list[Hyperlink] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)

    # Formatting
    font_name: str = ""
    font_size: float = 0.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    alignment: str = "left"
    style_name: str = ""
    list_type: str = ""  # "bullet", "numbered"
    list_level: int = 0
    indent: float = 0.0

    # Metadata
    page_number: int = 0
    section_number: str = ""
    language: str = ""


@dataclass(slots=True, frozen=True)
class DocumentMetadata:
    """Document-wide metadata extracted from the source file."""
    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: str = ""
    creator: str = ""
    producer: str = ""
    created_at: str = ""
    modified_at: str = ""
    page_count: int = 0
    word_count: int = 0
    character_count: int = 0

    # Page layout
    page_width: float = 0.0
    page_height: float = 0.0
    margin_top: float = 0.0
    margin_bottom: float = 0.0
    margin_left: float = 0.0
    margin_right: float = 0.0

    # DOCX specific
    default_font: str = ""
    default_font_size: float = 0.0
    line_spacing: float = 0.0

    # PDF specific
    pdf_version: str = ""
    is_encrypted: bool = False
    is_signed: bool = False
    is_tagged: bool = False
    has_acro_form: bool = False


# ─── Evidence ──────────────────────────────────────────────────────────────────

@dataclass(slots=True, frozen=True)
class EvidenceRange:
    """A single highlighted range within evidence."""
    text: str
    line_start: int
    line_end: int
    char_start: int = 0
    char_end: int = 0
    page_number: int = 0
    node_id: str = ""  # Reference to specific node
    confidence: float = 1.0


@dataclass(slots=True, frozen=True)
class Evidence:
    """Evidence attached to a review finding."""
    excerpt: str
    line_start: int
    line_end: int
    location: str
    source_location: SourceLocation | None = None
    page_number: int = 0
    block_ids: list[int] = field(default_factory=list)

    # Enhanced evidence
    node_ids: list[str] = field(default_factory=list)  # UUID references
    ranges: list[EvidenceRange] = field(default_factory=list)  # Multiple highlight ranges
    snippet_excerpt: str = ""  # Smart snippet with context
    snippet_before: str = ""  # Context before
    snippet_after: str = ""   # Context after
    confidence: float = 1.0


# ─── Document Model ────────────────────────────────────────────────────────────

@dataclass(slots=True, frozen=True)
class DocumentModel:
    """Normalized representation of a document used by the review pipeline."""
    filename: str
    content_type: str
    text: str
    lines: list[str]
    headings: list[tuple[int, str, int]]
    references: list[str]

    # Rich structure
    blocks: list[DocumentBlock] = field(default_factory=list)
    tables: list[TableData] = field(default_factory=list)
    figures: list[FigureData] = field(default_factory=list)
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)

    # Mapping from normalized text positions to source locations
    block_location_map: dict[int, SourceLocation] = field(default_factory=dict)
    # Text offset map (normalized ↔ original)
    offset_map: list[TextOffsetMapping] = field(default_factory=list)

    # Footnotes and endnotes
    footnotes: list[str] = field(default_factory=list)
    endnotes: list[str] = field(default_factory=list)

    # Hyperlinks and citations (global lists)
    hyperlinks: list[Hyperlink] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    equations: list[EquationData] = field(default_factory=list)

    # DOCX revision tracking
    revisions: list[dict[str, Any]] = field(default_factory=list)

    # Page structure
    page_breaks: list[int] = field(default_factory=list)
    pages: list[list[int]] = field(default_factory=list)

    # Sentences (flattened for sentence-level access)
    sentences: list[Sentence] = field(default_factory=list)


# ─── Existing types ────────────────────────────────────────────────────────────


@dataclass(slots=True, frozen=True)
class Issue:
    """A single review finding emitted by the rule engine or AI reviewer."""
    id: str
    category: str
    rule_id: str
    severity: Severity
    message: str
    recommendation: str
    evidence: Evidence
    confidence: int
    source: str
    autofix_allowed: bool = False


@dataclass(slots=True, frozen=True)
class ReviewRequest:
    """Input payload for a document review request."""
    text: str
    filename: str = "document.md"
    content_type: str = "text/markdown"
    profile_id: str = "academic"
    pack_ids: list[str] = field(default_factory=list)
    enabled_categories: list[str] | None = None


@dataclass(slots=True, frozen=True)
class ReviewResult:
    """Structured output returned after a review run completes."""
    profile_id: str
    pack_ids: list[str]
    issues: list[Issue]
    score: int
    category_scores: dict[str, int]
    summary: str
    report_markdown: str
    ai_review_enabled: bool = False
    ai_review_reason: str = ""
    duration_ms: float = 0.0
    doc_stats: dict[str, Any] = field(default_factory=dict)
    rule_stats: dict[str, Any] = field(default_factory=dict)
    pipeline_status: dict[str, Any] = field(default_factory=dict)
    detected_profile: str = ""
