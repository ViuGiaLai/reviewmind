from __future__ import annotations

from io import BytesIO
from pathlib import Path

from .text import TextParser
from ..models import DocumentModel


class UnsupportedDocumentError(ValueError):
    pass


class FileParser:
    """Transforms uploaded content into the engine's normalized model."""

    text_extensions = {".txt", ".md", ".markdown", ".html", ".htm", ".tex"}

    def __init__(self) -> None:
        self.text_parser = TextParser()

    def parse(self, content: bytes, filename: str, content_type: str = "") -> DocumentModel:
        suffix = Path(filename).suffix.casefold()
        if suffix in self.text_extensions:
            return self.text_parser.parse(content.decode("utf-8", errors="replace"), filename, content_type or "text/plain")
        if suffix == ".docx":
            return self._docx(content, filename, content_type)
        if suffix == ".pdf":
            return self._pdf(content, filename, content_type)
        raise UnsupportedDocumentError("Supported formats: TXT, Markdown, HTML, LaTex, DOCX and PDF.")

    def _docx(self, content: bytes, filename: str, content_type: str) -> DocumentModel:
        from docx import Document
        document = Document(BytesIO(content))
        text = "\n".join(
            f"{'#' * min(6, int(p.style.name[-1]))} {p.text}" if p.style.name.startswith("Heading") and p.style.name[-1:].isdigit() else p.text
            for p in document.paragraphs if p.text.strip()
        )
        return self.text_parser.parse(text, filename, content_type or "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    def _pdf(self, content: bytes, filename: str, content_type: str) -> DocumentModel:
        from pypdf import PdfReader
        text = "\n\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
        return self.text_parser.parse(text, filename, content_type or "application/pdf")
