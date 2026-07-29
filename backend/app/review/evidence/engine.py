from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..models import DocumentBlock, DocumentModel, Evidence, EvidenceRange, Sentence, SourceLocation


@dataclass
class EvidenceSnippet:
    """A smart evidence snippet with surrounding context."""
    highlighted: str
    before_context: str
    after_context: str
    ranges: list[EvidenceRange]
    page_number: int = 0
    block_index: int = -1
    node_ids: list[str] = field(default_factory=list)


@dataclass
class JumpTarget:
    """Target location for jump-to-location feature."""
    page_number: int = 0
    block_index: int = -1
    node_id: str = ""
    line_start: int = 0
    line_end: int = 0
    bbox: tuple[float, float, float, float] | None = None
    highlight_text: str = ""


class EvidenceEngine:
    """Generates evidence snippets, multi-range highlights, and jump targets."""

    # Sentence boundary detection
    # Known abbreviations that shouldn't trigger splits
    _ABBREVIATIONS = re.compile(
        r"\b(Dr|Mr|Mrs|Ms|Prof|Rev|Hon|St|Ave|Blvd|Rd|Fig|Eq|Vol|No|p|pp|vs|et al|e\.g|i\.e|etc|inc|ltd|co|dept|est|govt|sch|univ)\.",
        re.I,
    )
    _SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")
    _WHITESPACE = re.compile(r"\s+")

    # ── Snippet Generation ─────────────────────────────────────────────────

    def generate_snippet(
        self,
        text: str,
        line_start: int,
        line_end: int,
        context_lines: int = 2,
        max_chars: int = 500,
    ) -> EvidenceSnippet:
        """Generate a smart evidence snippet with surrounding context."""
        lines = text.split("\n")
        total_lines = len(lines)

        # Clamp bounds
        start = max(0, line_start - 1 - context_lines)
        end = min(total_lines, line_end + context_lines)

        # Extract context
        context_before = "\n".join(lines[start:max(0, line_start - 1)])
        evidence_text = "\n".join(lines[max(0, line_start - 1):min(total_lines, line_end)])
        context_after = "\n".join(lines[min(total_lines, line_end):end])

        # Truncate if too long
        if len(evidence_text) > max_chars:
            evidence_text = evidence_text[:max_chars] + "..."
        if len(context_before) > 200:
            context_before = "..." + context_before[-200:]
        if len(context_after) > 200:
            context_after = context_after[:200] + "..."

        # Build ranges
        ranges = [
            EvidenceRange(
                text=evidence_text,
                line_start=line_start,
                line_end=line_end,
                page_number=0,
            )
        ]

        return EvidenceSnippet(
            highlighted=evidence_text,
            before_context=context_before,
            after_context=context_after,
            ranges=ranges,
            page_number=0,
            block_index=line_start,
        )

    def generate_multi_range_snippet(
        self,
        text: str,
        ranges: list[tuple[int, int]],  # List of (line_start, line_end)
        context_lines: int = 1,
    ) -> EvidenceSnippet:
        """Generate evidence snippet with multiple highlight ranges."""
        lines = text.split("\n")
        all_ranges: list[EvidenceRange] = []

        for line_start, line_end in ranges:
            evidence_text = "\n".join(lines[max(0, line_start - 1):min(len(lines), line_end)])
            all_ranges.append(EvidenceRange(
                text=evidence_text,
                line_start=line_start,
                line_end=line_end,
            ))

        # Get context for the first and last range
        first_start = max(0, ranges[0][0] - 1 - context_lines) if ranges else 0
        last_end = min(len(lines), ranges[-1][1] + context_lines) if ranges else 0

        context_before = "\n".join(lines[first_start:max(0, ranges[0][0] - 1)]) if ranges else ""
        context_after = "\n".join(lines[min(len(lines), ranges[-1][1]):last_end]) if ranges else ""

        return EvidenceSnippet(
            highlighted="\n...\n".join(r.text for r in all_ranges),
            before_context=context_before,
            after_context=context_after,
            ranges=all_ranges,
        )

    # ── Sentence Splitting ─────────────────────────────────────────────────

    def split_sentences(self, text: str, block_id: str = "") -> list[Sentence]:
        """Split text into sentences with positions."""
        if not text.strip():
            return []

        # Replace abbreviation periods temporarily to avoid false splits
        protected = text
        abbr_map: dict[str, str] = {}
        for idx, m in enumerate(self._ABBREVIATIONS.finditer(text)):
            placeholder = f"\x00ABBR{idx}\x00"
            protected = protected.replace(m.group(), placeholder, 1)
            abbr_map[placeholder] = m.group()

        sentences: list[Sentence] = []
        parts = self._SENTENCE_BOUNDARY.split(protected)
        char_offset = 0

        for i, part in enumerate(parts):
            # Restore abbreviations
            for placeholder, original in abbr_map.items():
                part = part.replace(placeholder, original)
            part = part.strip()

            if not part:
                char_offset += 1
                continue

            sent = Sentence(
                text=part,
                index=i,
                start_char=char_offset,
                end_char=char_offset + len(part),
                block_id=block_id,
            )
            sentences.append(sent)
            char_offset += len(part) + 1

        return sentences

    # ── Jump-to-Location ───────────────────────────────────────────────────

    def build_jump_target(self, issue_evidence: Evidence, document: DocumentModel) -> JumpTarget | None:
        """Build a jump target from issue evidence."""
        if issue_evidence.source_location:
            loc = issue_evidence.source_location
            return JumpTarget(
                page_number=loc.page_number,
                block_index=loc.line_start - 1 if loc.line_start > 0 else -1,
                node_id=loc.node_id,
                line_start=loc.line_start,
                line_end=loc.line_end,
                bbox=loc.page_bbox if loc.page_bbox != (0, 0, 0, 0) else None,
                highlight_text=issue_evidence.excerpt,
            )

        # Try to find by block index
        block_idx = issue_evidence.line_start - 1
        if 0 <= block_idx < len(document.blocks):
            block = document.blocks[block_idx]
            return JumpTarget(
                page_number=block.page_number,
                block_index=block_idx,
                node_id=block.node_id,
                line_start=block.location.line_start,
                line_end=block.location.line_end,
                highlight_text=issue_evidence.excerpt,
            )

        # Try to find by line number
        for i, block in enumerate(document.blocks):
            if block.location.line_start <= issue_evidence.line_start <= block.location.line_end:
                return JumpTarget(
                    page_number=block.page_number,
                    block_index=i,
                    node_id=block.node_id,
                    line_start=issue_evidence.line_start,
                    line_end=issue_evidence.line_end,
                    highlight_text=issue_evidence.excerpt,
                )

        return None

    def build_jump_target_from_location(
        self,
        location: SourceLocation,
        document: DocumentModel,
    ) -> JumpTarget:
        """Build a jump target from a raw source location."""
        return JumpTarget(
            page_number=location.page_number,
            block_index=location.line_start - 1,
            node_id=location.node_id,
            line_start=location.line_start,
            line_end=location.line_end,
            bbox=location.page_bbox if location.page_bbox != (0, 0, 0, 0) else None,
        )

    # ── Evidence Enhancement ───────────────────────────────────────────────

    def enhance_evidence(
        self,
        evidence: Evidence,
        document: DocumentModel,
        context_lines: int = 2,
    ) -> Evidence:
        """Enhance an Evidence object with snippet context, ranges, and node references."""
        snippet = self.generate_snippet(
            text=document.text,
            line_start=evidence.line_start,
            line_end=evidence.line_end,
            context_lines=context_lines,
        )

        # Find referenced node IDs
        node_ids: list[str] = []
        for i, block in enumerate(document.blocks):
            if evidence.line_start <= block.location.line_start <= evidence.line_end:
                node_ids.append(block.node_id)
            if evidence.line_start <= block.location.line_end <= evidence.line_end:
                node_ids.append(block.node_id)

        return Evidence(
            excerpt=evidence.excerpt,
            line_start=evidence.line_start,
            line_end=evidence.line_end,
            location=evidence.location,
            source_location=evidence.source_location,
            page_number=evidence.page_number,
            block_ids=evidence.block_ids,
            node_ids=list(set(node_ids)),
            ranges=snippet.ranges,
            snippet_excerpt=snippet.highlighted,
            snippet_before=snippet.before_context,
            snippet_after=snippet.after_context,
            confidence=evidence.confidence,
        )


# Global instance
evidence_engine = EvidenceEngine()
