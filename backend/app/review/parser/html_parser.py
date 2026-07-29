from __future__ import annotations

import re
from html.parser import HTMLParser as BaseHTMLParser
from typing import Any

from ..models import (
    BlockType,
    DocumentBlock,
    DocumentMetadata,
    DocumentModel,
    SourceLocation,
)
from .text import TextParser


class HtmlParser:
    """Extracts semantic content from HTML documents, stripping non-content elements."""

    # Tags to strip entirely (with content)
    STRIP_TAGS = {
        "script", "style", "nav", "header", "footer", "aside",
        "noscript", "iframe", "svg", "canvas", "form", "input",
        "select", "textarea", "button", "label",
    }

    # Tags that are block-level
    BLOCK_TAGS = {
        "p", "div", "section", "article", "main", "blockquote",
        "pre", "address", "hr", "br",
    }

    # Tags that represent headings
    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    # Tags that represent lists
    LIST_TAGS = {"ul", "ol", "dl", "li"}

    # Tags that represent tables
    TABLE_TAGS = {"table", "tr", "td", "th", "thead", "tbody", "tfoot", "caption"}

    def __init__(self) -> None:
        self.text_parser = TextParser()

    def parse(self, content: bytes, filename: str, content_type: str) -> DocumentModel:
        html_text = content.decode("utf-8", errors="replace")

        # Parse with structured extraction
        extractor = _HtmlExtractor()
        extractor.feed(html_text)

        blocks = extractor.blocks
        metadata = extractor.metadata

        # Build text + lines for backward compatibility
        text_lines: list[str] = []
        for b in blocks:
            if b.text:
                text_lines.append(b.text)
        text = "\n".join(text_lines)

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
            metadata=metadata or DocumentMetadata(),
        )


class _HtmlExtractor(BaseHTMLParser):
    """HTML parser that extracts structured blocks, stripping scripts/styles/navigation."""

    STRIP_TAGS = {
        "script", "style", "nav", "header", "footer", "aside",
        "noscript", "iframe", "svg", "canvas", "form", "input",
        "select", "textarea", "button", "label",
    }

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[DocumentBlock] = []
        self.metadata: DocumentMetadata | None = None

        # State
        self._stack: list[str] = []  # Tag stack
        self._current_text: list[str] = []
        self._current_tag: str = ""
        self._current_attrs: dict[str, str] = {}
        self._skip_depth: int = 0  # How many levels deep to skip
        self._in_table: bool = False
        self._table_cells: list[str] = []
        self._title: str = ""
        self._in_title: bool = False
        self._meta_data: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr_dict = {k: v or "" for k, v in attrs}

        self._stack.append(tag)

        # Skip depth management for strip tags
        if self._skip_depth > 0:
            if tag in self.STRIP_TAGS:
                self._skip_depth += 1
            return

        # Check if this tag should be stripped
        if tag in self.STRIP_TAGS:
            self._skip_depth = 1
            return

        # Track title
        if tag == "title":
            self._in_title = True
            self._current_text = []
            return

        # Track meta
        if tag == "meta":
            name = attr_dict.get("name", "").lower()
            content = attr_dict.get("content", "")
            if name in ("author", "description", "keywords", "subject"):
                self._meta_data[name] = content

        # Flush current text block
        self._flush_text()

        # Track current tag
        self._current_tag = tag
        self._current_attrs = attr_dict

        # Table cell tracking
        if tag in ("td", "th"):
            self._current_text = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        # Pop stack and handle skip depth
        if self._stack:
            self._stack.pop()

        if self._skip_depth > 0:
            if tag in self.STRIP_TAGS:
                self._skip_depth -= 1
            return

        if tag == "title":
            self._in_title = False
            title_text = "".join(self._current_text).strip()
            if title_text:
                self._title = title_text
            self._current_text = []
            return

        # Flush text for block-level closing tags
        if tag in self.BLOCK_TAGS or tag in self.HEADING_TAGS or tag in self.LIST_TAGS or tag in ("td", "th"):
            self._flush_text()

        # Handle table cell
        if tag in ("td", "th"):
            cell_text = "".join(self._current_text).strip()
            self._table_cells.append(cell_text)
            self._current_text = []

        # Handle table row
        if tag == "tr" and self._table_cells:
            row_text = " | ".join(self._table_cells)
            if row_text.strip():
                self.blocks.append(DocumentBlock(
                    type=BlockType.TABLE,
                    text=row_text,
                    location=SourceLocation(),
                ))
            self._table_cells = []

        # Handle list item
        if tag == "li" and self._current_text:
            text = "".join(self._current_text).strip()
            if text:
                self.blocks.append(DocumentBlock(
                    type=BlockType.LIST_ITEM,
                    text=text,
                    location=SourceLocation(),
                ))
            self._current_text = []

        # Track caption
        if tag == "caption" and self._current_text:
            text = "".join(self._current_text).strip()
            if text:
                self.blocks.append(DocumentBlock(
                    type=BlockType.CAPTION,
                    text=text,
                    location=SourceLocation(),
                ))

        # Figure tag detection
        if tag == "figure":
            self._flush_text()

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        self._current_text.append(data)

    def handle_entityref(self, name: str) -> None:
        if self._skip_depth > 0:
            return
        char = self._convert_entity(name)
        self._current_text.append(char)

    def handle_charref(self, name: str) -> None:
        if self._skip_depth > 0:
            return
        try:
            if name.startswith("x"):
                char = chr(int(name[1:], 16))
            else:
                char = chr(int(name))
            self._current_text.append(char)
        except (ValueError, OverflowError):
            self._current_text.append(f"&#{name};")

    def _flush_text(self) -> None:
        """Flush accumulated text as a block."""
        text = "".join(self._current_text).strip()
        if not text:
            self._current_text = []
            return

        tag = self._current_tag

        # Determine block type
        if tag in self.HEADING_TAGS:
            level = int(tag[1])
            self.blocks.append(DocumentBlock(
                type=BlockType.HEADING,
                text=text,
                level=level,
                location=SourceLocation(),
            ))
        elif tag == "blockquote":
            self.blocks.append(DocumentBlock(
                type=BlockType.PARAGRAPH,
                text=text,
                location=SourceLocation(),
            ))
        elif tag in ("pre", "code"):
            self.blocks.append(DocumentBlock(
                type=BlockType.CODE_BLOCK,
                text=text,
                location=SourceLocation(),
            ))
        elif tag == "hr":
            self.blocks.append(DocumentBlock(
                type=BlockType.PAGE_BREAK,
                text="[HORIZONTAL RULE]",
                location=SourceLocation(),
            ))
        elif tag in ("td", "th"):
            # Handled in end tag
            pass
        else:
            # Regular paragraph
            self.blocks.append(DocumentBlock(
                type=BlockType.PARAGRAPH,
                text=text,
                location=SourceLocation(),
            ))

        self._current_text = []

    def _convert_entity(self, name: str) -> str:
        """Convert HTML entity name to character."""
        entities = {
            "amp": "&", "lt": "<", "gt": ">", "quot": "\"",
            "apos": "'", "nbsp": " ", "copy": "©", "reg": "®",
            "trade": "™", "mdash": "—", "ndash": "–",
            "ldquo": "\u201c", "rdquo": "\u201d", "lsquo": "\u2018",
            "rsquo": "\u2019", "bull": "•", "hellip": "…",
            "tilde": "~",
        }
        return entities.get(name, f"&{name};")

    def close(self) -> None:
        super().close()
        self._flush_text()

        # Set metadata from what we collected
        self.metadata = DocumentMetadata(
            title=self._title,
            author=self._meta_data.get("author", ""),
            subject=self._meta_data.get("subject", "") or self._meta_data.get("description", ""),
            keywords=self._meta_data.get("keywords", ""),
        )
