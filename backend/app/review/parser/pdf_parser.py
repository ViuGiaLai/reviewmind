from __future__ import annotations

import re
from io import BytesIO
from typing import Any

from pypdf import PdfReader
from pypdf.generic import RectangleObject

from ..models import (
    BlockType,
    DocumentBlock,
    DocumentMetadata,
    DocumentModel,
    FigureData,
    SourceLocation,
    TableData,
)
from .text import TextParser


class PdfParser:
    """Comprehensive PDF parser with page numbers, block coordinates, and evidence mapping."""

    # Patterns for common structures
    _figure_caption = re.compile(
        r"^(Figure|Fig\.|Hình|Figure\s+\d+|Fig\.\s+\d+)\s*[.:]?\s*(.+)$", re.I
    )
    _table_caption = re.compile(
        r"^(Table|Bảng|Table\s+\d+|Bảng\s+\d+)\s*[.:]?\s*(.+)$", re.I
    )
    _heading_pattern = re.compile(
        r"^(?:CHAPTER|SECTION|APPENDIX|PHỤ LỤC|CHƯƠNG)\s+[\dIVXL\.]+\s*[:.]?\s*(.+)$", re.I
    )
    _numbering_heading = re.compile(
        r"^(\d+(?:\.\d+)*)\s+(.+)$"
    )

    def __init__(self) -> None:
        self.text_parser = TextParser()

    # ── Main Entry ─────────────────────────────────────────────────────────────

    def parse(self, content: bytes, filename: str, content_type: str) -> DocumentModel:
        reader = PdfReader(BytesIO(content))
        blocks: list[DocumentBlock] = []
        figures: list[FigureData] = []
        tables: list[TableData] = []
        footnotes: list[str] = []
        page_breaks: list[int] = []
        block_idx = 0
        total_chars = 0

        # ── Metadata ──────────────────────────────────────────────────────────
        metadata = self._extract_metadata(reader)

        # ── Pages ──────────────────────────────────────────────────────────────
        pages: list[list[int]] = []

        for page_num, page in enumerate(reader.pages, start=1):
            page_blocks_start = block_idx

            # Get page text with position info
            page_text = page.extract_text() or ""
            if not page_text.strip():
                pages.append([])
                continue

            # Try to get text with positioning (layout mode)
            try:
                page_text_layout = page.extract_text(extraction_mode="layout")
            except Exception:
                page_text_layout = page_text

            # Page dimensions
            mediabox = page.mediabox
            page_width = float(mediabox.width) if mediabox else 0
            page_height = float(mediabox.height) if mediabox else 0

            # Extract images
            page_figures = self._extract_images(page)
            figures.extend(page_figures)

            # Extract annotations (links, comments)
            annotations = self._extract_annotations(page)

            # Split page into blocks (paragraphs)
            page_blocks = self._split_page_blocks(
                page_text, page_text_layout, page_num, page_width, page_height,
            )
            blocks.extend(page_blocks)
            block_idx += len(page_blocks)

            total_chars += len(page_text)

            # Track page boundaries
            page_breaks.append(block_idx)
            pages.append(list(range(page_blocks_start, block_idx)))

        # ── Detect tables across pages ────────────────────────────────────────
        # Simple table detection: lines with consistent spacing
        for i, block in enumerate(blocks):
            if self._looks_like_table(block.text):
                table_data = self._parse_table_from_text(block)
                if table_data:
                    tables.append(table_data)
                    # Replace block with table block
                    from dataclasses import replace
                    blocks[i] = replace(block, type=BlockType.TABLE, table=table_data)

        # ── Build text + lines for backward compatibility ──────────────────────
        text_lines: list[str] = []
        for b in blocks:
            if b.text:
                text_lines.append(b.text)
        text = "\n".join(text_lines)

        # Build block_location_map
        block_location_map: dict[int, SourceLocation] = {}
        for i, b in enumerate(blocks):
            if b.location.page_number > 0:
                block_location_map[i] = b.location

        # Use TextParser for headings/references backward compat
        base = self.text_parser.parse(text, filename, content_type)

        return DocumentModel(
            filename=filename,
            content_type=content_type,
            text=text,
            lines=text_lines,
            headings=base.headings,
            references=base.references,
            blocks=blocks,
            tables=tables,
            figures=figures,
            metadata=metadata,
            block_location_map=block_location_map,
            footnotes=footnotes,
            page_breaks=[p for p in page_breaks if p < len(blocks)],
            pages=pages,
        )

    # ── Metadata ───────────────────────────────────────────────────────────────

    def _extract_metadata(self, reader: PdfReader) -> DocumentMetadata:
        meta = reader.metadata or {}

        # Page dimensions from first page
        page_width = page_height = 0.0
        if reader.pages:
            mb = reader.pages[0].mediabox
            if mb:
                page_width = float(mb.width)
                page_height = float(mb.height)

        # Word count approximation
        word_count = 0
        char_count = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            word_count += len(text.split())
            char_count += len(text)

        return DocumentMetadata(
            title=str(meta.get("/Title", "")),
            author=str(meta.get("/Author", "")),
            subject=str(meta.get("/Subject", "")),
            keywords=str(meta.get("/Keywords", "")),
            creator=str(meta.get("/Creator", "")),
            producer=str(meta.get("/Producer", "")),
            created_at=str(meta.get("/CreationDate", "")),
            modified_at=str(meta.get("/ModDate", "")),
            page_count=len(reader.pages),
            word_count=word_count,
            character_count=char_count,
            page_width=page_width,
            page_height=page_height,
            pdf_version=str(reader.pdf_header) if hasattr(reader, "pdf_header") else "",
            is_encrypted=reader.is_encrypted,
        )

    # ── Image Extraction ──────────────────────────────────────────────────────

    def _extract_images(self, page: Any) -> list[FigureData]:
        figures: list[FigureData] = []
        try:
            if "/XObject" in page["/Resources"]:
                xobjects = page["/Resources"]["/XObject"].get_object()
                for obj_name in xobjects:
                    obj = xobjects[obj_name].get_object()
                    if obj.get("/Subtype") == "/Image":
                        # Get image dimensions
                        width = obj.get("/Width", 0)
                        height = obj.get("/Height", 0)
                        figures.append(FigureData(
                            alt_text=f"[Image: {obj_name}]",
                            width=float(width),
                            height=float(height),
                        ))
        except Exception:
            pass
        return figures

    # ── Annotation Extraction ──────────────────────────────────────────────────

    def _extract_annotations(self, page: Any) -> list[dict[str, Any]]:
        annotations: list[dict[str, Any]] = []
        try:
            if "/Annots" in page:
                for annot in page["/Annots"]:
                    a = annot.get_object()
                    a_type = a.get("/Subtype", "")
                    a_text = a.get("/Contents", "")
                    rect = a.get("/Rect", None)
                    annotations.append({
                        "type": a_type,
                        "text": str(a_text),
                        "rect": [float(r) for r in rect] if rect else [],
                    })
        except Exception:
            pass
        return annotations

    # ── Page Block Splitting ──────────────────────────────────────────────────

    def _split_page_blocks(
        self,
        page_text: str,
        page_text_layout: str,
        page_num: int,
        page_width: float,
        page_height: float,
    ) -> list[DocumentBlock]:
        blocks: list[DocumentBlock] = []

        # Split by double newlines (paragraphs)
        raw_paragraphs = re.split(r"\n\s*\n", page_text)
        layout_paragraphs = re.split(r"\n\s*\n", page_text_layout) if page_text_layout != page_text else []

        for i, para_text in enumerate(raw_paragraphs):
            para_text = para_text.strip()
            if not para_text:
                continue

            layout_text = layout_paragraphs[i] if i < len(layout_paragraphs) else para_text

            # Detect block type
            block_type, level = self._detect_block_type(para_text)

            # Estimate coordinates from layout text
            loc = self._estimate_location(layout_text, page_num, page_width, page_height, i)

            blocks.append(DocumentBlock(
                type=block_type,
                text=para_text[:2000],  # Truncate very long blocks
                level=level,
                location=loc,
                page_number=page_num,
                alignment=self._detect_alignment(layout_text),
            ))

            # Extract footnote-like content
            if self._looks_like_footnote(para_text):
                blocks[-1] = DocumentBlock(
                    type=BlockType.FOOTNOTE,
                    text=para_text,
                    location=loc,
                    page_number=page_num,
                )

        return blocks

    # ── Block Type Detection ───────────────────────────────────────────────────

    def _detect_block_type(self, text: str) -> tuple[BlockType, int]:
        """Detect the type of a text block."""
        # Heading detection
        if self._heading_pattern.match(text):
            return BlockType.HEADING, 1

        m = self._numbering_heading.match(text)
        if m:
            num_part = m.group(1)
            depth = len(num_part.split("."))
            return BlockType.HEADING, depth

        # All caps short lines = likely heading
        stripped = text.strip()
        if len(stripped) < 100 and stripped.isupper() and len(stripped.split()) <= 8:
            return BlockType.HEADING, 2

        # Figure caption
        if self._figure_caption.match(text):
            return BlockType.CAPTION, 0

        # Table caption
        if self._table_caption.match(text):
            return BlockType.CAPTION, 0

        return BlockType.PARAGRAPH, 0

    def _looks_like_footnote(self, text: str) -> bool:
        """Check if text looks like a footnote (starts with small number/symbol)."""
        return bool(re.match(r"^[\d†‡*]\s+", text.strip()))

    def _looks_like_table(self, text: str) -> bool:
        """Check if text looks like tabular data."""
        lines = text.strip().split("\n")
        if len(lines) < 2:
            return False
        # Check for consistent spacing/tabs
        for line in lines:
            if "\t" in line:
                return True
        # Check for pipe table
        if any(line.startswith("|") for line in lines):
            return True
        return False

    def _parse_table_from_text(self, block: DocumentBlock) -> TableData | None:
        """Parse a table from text block."""
        lines = block.text.strip().split("\n")
        if len(lines) < 2:
            return None

        from ..models import TableCell

        cells: list[TableCell] = []
        for row_idx, line in enumerate(lines):
            # Split by tab or pipe
            if "|" in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
            elif "\t" in line:
                parts = [p.strip() for p in line.split("\t") if p.strip()]
            else:
                parts = [line.strip()]

            for col_idx, part in enumerate(parts):
                if part and part != "---":  # Skip separator rows
                    cells.append(TableCell(
                        text=part,
                        row=row_idx,
                        col=col_idx,
                    ))

        if not cells:
            return None

        max_col = max(c.col for c in cells) + 1
        return TableData(
            rows=len(lines),
            cols=max_col,
            cells=cells,
            location=block.location,
        )

    def _detect_alignment(self, text: str) -> str:
        """Simple alignment detection based on whitespace distribution."""
        lines = text.strip().split("\n")
        if not lines:
            return "left"

        centered_count = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Check if line has roughly equal whitespace on both sides
            leading = len(line) - len(line.lstrip())
            trailing = len(line.rstrip()) - len(stripped)
            if abs(leading - trailing) < 3:
                centered_count += 1

        total_valid = sum(1 for l in lines if l.strip())
        if total_valid > 0 and centered_count / total_valid > 0.7:
            return "center"
        return "left"

    def _estimate_location(
        self, text: str, page_num: int, page_width: float, page_height: float, block_index: int
    ) -> SourceLocation:
        """Estimate source location from layout text."""
        # Approximate position based on text characteristics
        lines = text.split("\n")
        y_pos = page_height - (block_index * 15)  # Rough estimate

        return SourceLocation(
            page_number=page_num,
            page_label=f"Page {page_num}",
            y=y_pos,
            x=10.0,
            page_bbox=(0, y_pos - len(lines) * 12, page_width, y_pos),
        )
