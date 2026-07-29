from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentChunk:
    """A single chunk of a larger document."""
    index: int
    text: str
    start_char: int
    end_char: int
    start_line: int
    end_line: int
    metadata: dict[str, Any] = field(default_factory=dict)


class ChunkingEngine:
    """Splits long documents into chunks for LLM processing."""

    # Semantic boundaries that we prefer to split on (in priority order)
    BOUNDARY_PATTERNS = [
        re.compile(r"\n#{1,3}\s+.+\n"),       # Headings (## or ###)
        re.compile(r"\n\n"),                   # Paragraph breaks
        re.compile(r"\n"),                     # Line breaks
        re.compile(r"[.!?]\s+"),               # Sentence ends
    ]

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 8000,
        chunk_overlap: int = 500,
        respect_boundaries: bool = True,
    ) -> list[DocumentChunk]:
        """Split text into chunks, respecting semantic boundaries when possible."""
        if len(text) <= chunk_size:
            return [
                DocumentChunk(
                    index=0, text=text,
                    start_char=0, end_char=len(text),
                    start_line=1, end_line=len(text.split("\n")),
                )
            ]

        chunks: list[DocumentChunk] = []
        start = 0
        chunk_idx = 0
        lines = text.split("\n")

        while start < len(text):
            # Determine end point for this chunk
            end = min(start + chunk_size, len(text))

            if respect_boundaries and end < len(text):
                end = self._find_boundary(text, start, end)

            chunk_text = text[start:end]

            # Calculate line numbers
            start_line = text[:start].count("\n") + 1
            end_line = text[:end].count("\n") + 1

            chunks.append(DocumentChunk(
                index=chunk_idx,
                text=chunk_text,
                start_char=start,
                end_char=end,
                start_line=start_line,
                end_line=end_line,
                metadata={
                    "chunk_of_total": f"{chunk_idx + 1}/{(len(text) // chunk_size) + 1}",
                },
            ))

            # Move start, accounting for overlap
            start = end - (chunk_overlap if end < len(text) else 0)
            chunk_idx += 1

        return chunks

    def _find_boundary(self, text: str, start: int, end: int) -> int:
        """Find the best boundary position near the end of a chunk."""
        search_region = text[max(start, end - 500):end + 200]

        # Try to find a heading boundary first (work backwards from end)
        for pattern in self.BOUNDARY_PATTERNS:
            matches = list(pattern.finditer(search_region))
            if matches:
                # Find the last match that's within reasonable range
                for m in reversed(matches):
                    boundary = max(start, start + (end - len(search_region)) + m.end())
                    if boundary >= start and boundary <= end:
                        return boundary

        # If no boundary found, just use the exact end
        return end

    def chunk_by_sections(
        self,
        text: str,
        max_section_length: int = 4000,
    ) -> list[DocumentChunk]:
        """Split text by markdown headings (sections)."""
        heading_pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

        sections: list[tuple[int, int, str]] = []  # (start, end, heading)
        last_heading = "document-start"
        last_pos = 0

        for m in heading_pattern.finditer(text):
            if last_pos > 0:
                sections.append((last_pos, m.start(), last_heading))
            last_heading = m.group(2)
            last_pos = m.start()

        if last_pos < len(text):
            sections.append((last_pos, len(text), last_heading))

        chunks = []
        for i, (sec_start, sec_end, heading) in enumerate(sections):
            sec_text = text[sec_start:sec_end]
            if len(sec_text) > max_section_length:
                # Split long section further
                sub_chunks = self.chunk_text(
                    sec_text,
                    chunk_size=max_section_length,
                    chunk_overlap=100,
                    respect_boundaries=True,
                )
                for sc in sub_chunks:
                    sc.metadata["section"] = heading
                    chunks.append(sc)
            else:
                chunks.append(DocumentChunk(
                    index=len(chunks),
                    text=sec_text,
                    start_char=sec_start,
                    end_char=sec_end,
                    start_line=text[:sec_start].count("\n") + 1,
                    end_line=text[:sec_end].count("\n") + 1,
                    metadata={"section": heading},
                ))

        return chunks

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text (rough heuristic)."""
        # Rough: 1 token ≈ 4 chars for English
        return len(text) // 4

    def truncate_to_token_limit(
        self,
        text: str,
        max_tokens: int,
        from_start: bool = True,
    ) -> str:
        """Truncate text to fit within token limit."""
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text

        if from_start:
            return text[:max_chars] + "\n\n[...truncated...]"
        else:
            return "[...truncated...]\n\n" + text[-max_chars:]


# Global instance
chunking_engine = ChunkingEngine()
