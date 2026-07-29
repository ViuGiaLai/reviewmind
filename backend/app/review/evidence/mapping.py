from __future__ import annotations

from typing import Any

from ..models import DocumentModel, SourceLocation, TextOffsetMapping


class TextOffsetMapper:
    """Maps between normalized text positions and original source positions.

    Provides:
    - normalized_to_original(offset) → original char offset
    - original_to_normalized(offset) → normalized char offset
    - get_location_at(normalized_offset) → SourceLocation
    """

    def build_mapping(self, document: DocumentModel) -> list[TextOffsetMapping]:
        """Build offset mapping from document blocks."""
        mappings: list[TextOffsetMapping] = []
        normalized_offset = 0

        for i, block in enumerate(document.blocks):
            if not block.text:
                continue

            block_text = block.text
            block_len = len(block_text)

            mappings.append(TextOffsetMapping(
                normalized_start=normalized_offset,
                normalized_end=normalized_offset + block_len,
                original_start=normalized_offset,  # Same for normalized text
                original_end=normalized_offset + block_len,
                source_location=block.location,
            ))

            # +1 for newline separator
            normalized_offset += block_len + 1

        return mappings

    def get_location_at(
        self,
        normalized_offset: int,
        mappings: list[TextOffsetMapping],
    ) -> SourceLocation | None:
        """Get source location for a normalized text offset."""
        for mapping in mappings:
            if mapping.normalized_start <= normalized_offset <= mapping.normalized_end:
                return mapping.source_location
        return None

    def get_block_index_at(
        self,
        normalized_offset: int,
        document: DocumentModel,
    ) -> int:
        """Get block index for a normalized text offset."""
        offset = 0
        for i, block in enumerate(document.blocks):
            block_len = len(block.text) if block.text else 0
            if offset <= normalized_offset <= offset + block_len:
                return i
            offset += block_len + 1
        return -1

    def get_page_for_offset(
        self,
        normalized_offset: int,
        document: DocumentModel,
    ) -> int:
        """Get page number for a normalized text offset."""
        block_idx = self.get_block_index_at(normalized_offset, document)
        if block_idx >= 0 and block_idx < len(document.blocks):
            return document.blocks[block_idx].page_number
        # Search page breaks
        for i, pb in enumerate(document.page_breaks):
            if pb > block_idx:
                return i + 1
        return 1


# Global instance
text_offset_mapper = TextOffsetMapper()
