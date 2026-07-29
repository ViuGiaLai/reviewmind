from __future__ import annotations

from io import BytesIO
from pathlib import Path

from ..models import DocumentModel
from .docx_parser import DocxParser
from .html_parser import HtmlParser
from .pdf_parser import PdfParser
from .text import TextParser


class UnsupportedDocumentError(ValueError):
    pass


class FileParser:
    """Transforms uploaded content into the engine's normalized model with rich structure."""

    text_extensions = {".txt", ".md", ".markdown"}
    html_extensions = {".html", ".htm"}
    tex_extensions = {".tex"}

    def __init__(self) -> None:
        self.text_parser = TextParser()
        self.docx_parser = DocxParser()
        self.pdf_parser = PdfParser()
        self.html_parser = HtmlParser()

    def parse(self, content: bytes, filename: str, content_type: str = "") -> DocumentModel:
        """Parse document content from bytes."""
        suffix = Path(filename).suffix.casefold()

        # Plain text / Markdown
        if suffix in self.text_extensions:
            text = content.decode("utf-8", errors="replace")
            return self.text_parser.parse(text, filename, content_type or "text/plain")

        # HTML
        if suffix in self.html_extensions:
            return self.html_parser.parse(content, filename, content_type or "text/html")

        # LaTeX
        if suffix in self.tex_extensions:
            text = content.decode("utf-8", errors="replace")
            return self.text_parser.parse(text, filename, content_type or "text/x-tex")

        # DOCX
        if suffix == ".docx":
            return self.docx_parser.parse(
                content, filename,
                content_type or "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        # PDF
        if suffix == ".pdf":
            return self.pdf_parser.parse(content, filename, content_type or "application/pdf")

        raise UnsupportedDocumentError("Supported formats: TXT, Markdown, HTML, LaTex, DOCX and PDF.")

    def parse_text(self, text: str, filename: str, content_type: str = "") -> DocumentModel:
        """Parse text directly without encode/decode cycle."""
        return self.text_parser.parse(text, filename, content_type)
