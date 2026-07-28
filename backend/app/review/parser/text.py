from __future__ import annotations

import re

from ..models import DocumentModel


class TextParser:
    """Normalizes Markdown/plain text. Binary format parsers plug in behind this contract."""

    _heading = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
    _reference_heading = re.compile(r"^(references|bibliography|tài liệu tham khảo)$", re.I)

    def parse(self, text: str, filename: str, content_type: str) -> DocumentModel:
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        headings: list[tuple[int, str, int]] = []
        references: list[str] = []
        in_references = False
        for index, line in enumerate(lines, start=1):
            match = self._heading.match(line)
            if match:
                title = match.group(2)
                headings.append((len(match.group(1)), title, index))
                in_references = bool(self._reference_heading.match(title))
                continue
            if in_references and line.strip():
                references.append(line.strip())
        return DocumentModel(filename, content_type, "\n".join(lines), lines, headings, references)
