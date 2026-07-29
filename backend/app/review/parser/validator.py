from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..models import DocumentModel

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of parser validation."""
    valid: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


class ParserValidator:
    """Validates parser output for correctness and completeness."""

    MAX_BLOCK_TEXT_LENGTH = 100_000  # 100KB max per block
    MAX_TOTAL_TEXT_LENGTH = 50_000_000  # 50MB max total
    MIN_BLOCKS = 1
    MAX_BLOCKS = 100_000

    def validate(self, document: DocumentModel) -> ValidationResult:
        """Validate a parsed document model."""
        result = ValidationResult()

        # Basic structure checks
        if not document.text and not document.blocks:
            result.errors.append("Document has no text content and no blocks")
            result.valid = False
            return result

        if len(document.text) > self.MAX_TOTAL_TEXT_LENGTH:
            result.warnings.append(
                f"Document text exceeds {self.MAX_TOTAL_TEXT_LENGTH // 1_000_000}MB "
                f"({len(document.text)} chars)"
            )

        # Validate blocks
        if len(document.blocks) < self.MIN_BLOCKS:
            result.warnings.append(f"Document has fewer than {self.MIN_BLOCKS} blocks")
        if len(document.blocks) > self.MAX_BLOCKS:
            result.warnings.append(f"Document has {len(document.blocks)} blocks, may impact performance")

        for i, block in enumerate(document.blocks):
            # Check text length
            if len(block.text) > self.MAX_BLOCK_TEXT_LENGTH:
                result.warnings.append(f"Block {i} text exceeds {self.MAX_BLOCK_TEXT_LENGTH // 1000}KB")

            # Check node_id uniqueness
            for j in range(i + 1, min(i + 10, len(document.blocks))):
                if document.blocks[j].node_id == block.node_id:
                    result.errors.append(f"Duplicate node_id at blocks {i} and {j}")

            # Check sentence positions
            if block.sentences:
                total_sent_chars = sum(
                    s.end_char - s.start_char for s in block.sentences
                )
                if total_sent_chars > len(block.text) * 1.1:
                    result.warnings.append(
                        f"Block {i}: sentence char range exceeds block text length"
                    )

        # Validate pages
        if document.pages:
            total_page_blocks = sum(len(p) for p in document.pages)
            if total_page_blocks != len(document.blocks):
                result.warnings.append(
                    f"Page block count ({total_page_blocks}) != total blocks ({len(document.blocks)})"
                )

        # Validate offset mapping
        if document.offset_map:
            last_end = 0
            for i, m in enumerate(document.offset_map):
                if m.normalized_start < last_end:
                    result.warnings.append(f"Offset mapping {i}: overlapping normalized ranges")
                last_end = m.normalized_end

        # Collect stats
        result.stats = {
            "blocks": len(document.blocks),
            "total_chars": len(document.text),
            "total_lines": len(document.lines),
            "headings": len(document.headings),
            "tables": len(document.tables),
            "figures": len(document.figures),
            "footnotes": len(document.footnotes),
            "sentences": sum(len(b.sentences) for b in document.blocks),
            "hyperlinks": len(document.hyperlinks) + sum(len(b.hyperlinks) for b in document.blocks),
            "citations": len(document.citations) + sum(len(b.citations) for b in document.blocks),
            "pages": len(document.pages),
            "page_breaks": len(document.page_breaks),
            "has_offset_map": len(document.offset_map) > 0,
            "has_node_ids": any(b.node_id for b in document.blocks[:5]),
        }

        return result

    def check_corrupted(self, content: bytes, filename: str) -> str | None:
        """Check if a file appears corrupted before parsing."""
        import struct
        from pathlib import Path

        suffix = Path(filename).suffix.casefold()

        if suffix == ".pdf":
            if len(content) < 10:
                return "File too small to be a valid PDF"
            if content[:5] != b"%PDF-":
                return "File does not start with PDF header"
            # Check for EOF marker
            if b"%%EOF" not in content[-100:]:
                return "PDF missing end-of-file marker"

        elif suffix == ".docx":
            if len(content) < 22:
                return "File too small to be a valid DOCX"
            # DOCX is a ZIP file
            if content[:2] != b"PK":
                return "File does not start with ZIP header (invalid DOCX)"

        elif suffix in (".txt", ".md", ".markdown"):
            try:
                content.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    content.decode("latin-1")
                except UnicodeDecodeError:
                    return "File is not valid UTF-8 or Latin-1 text"

        return None  # No corruption detected


# Global instance
parser_validator = ParserValidator()
