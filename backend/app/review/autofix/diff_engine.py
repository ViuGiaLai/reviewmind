from __future__ import annotations

import difflib
import re
from typing import Any

from .models import DiffLine


class DiffEngine:
    """Generates diffs at word, line, and paragraph levels."""

    def line_diff(self, original: str, suggested: str) -> list[DiffLine]:
        """Generate a line-by-line diff."""
        orig_lines = original.split("\n")
        sugg_lines = suggested.split("\n")
        result: list[DiffLine] = []

        matcher = difflib.SequenceMatcher(None, orig_lines, sugg_lines)
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "equal":
                for idx in range(i1, i2):
                    result.append(DiffLine(
                        type="same",
                        old_line=idx + 1,
                        new_line=idx + 1 + (j1 - i1),
                        old_text=orig_lines[idx],
                        new_text=orig_lines[idx],
                    ))
            elif op == "replace":
                for idx in range(i1, i2):
                    result.append(DiffLine(
                        type="removed",
                        old_line=idx + 1,
                        old_text=orig_lines[idx],
                    ))
                for idx in range(j1, j2):
                    result.append(DiffLine(
                        type="added",
                        new_line=idx + 1,
                        new_text=sugg_lines[idx],
                    ))
            elif op == "delete":
                for idx in range(i1, i2):
                    result.append(DiffLine(
                        type="removed",
                        old_line=idx + 1,
                        old_text=orig_lines[idx],
                    ))
            elif op == "insert":
                for idx in range(j1, j2):
                    result.append(DiffLine(
                        type="added",
                        new_line=idx + 1,
                        new_text=sugg_lines[idx],
                    ))

        return result

    def word_diff(self, original: str, suggested: str) -> list[dict[str, Any]]:
        """Generate a word-level diff for inline highlighting."""
        orig_words = re.findall(r"\S+\s*", original)
        sugg_words = re.findall(r"\S+\s*", suggested)
        result: list[dict[str, Any]] = []

        matcher = difflib.SequenceMatcher(None, orig_words, sugg_words)
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "equal":
                result.append({"type": "same", "text": "".join(orig_words[i1:i2])})
            elif op == "replace":
                if i1 < i2:
                    result.append({"type": "removed", "text": "".join(orig_words[i1:i2])})
                if j1 < j2:
                    result.append({"type": "added", "text": "".join(sugg_words[j1:j2])})
            elif op == "delete":
                if i1 < i2:
                    result.append({"type": "removed", "text": "".join(orig_words[i1:i2])})
            elif op == "insert":
                if j1 < j2:
                    result.append({"type": "added", "text": "".join(sugg_words[j1:j2])})

        return result

    def paragraph_diff(self, original: str, suggested: str) -> list[dict[str, Any]]:
        """Generate a paragraph-level diff."""
        orig_paras = [p.strip() for p in original.split("\n\n") if p.strip()]
        sugg_paras = [p.strip() for p in suggested.split("\n\n") if p.strip()]
        result: list[dict[str, Any]] = []

        matcher = difflib.SequenceMatcher(None, orig_paras, sugg_paras)
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "equal":
                for idx in range(i1, i2):
                    result.append({"type": "same", "text": orig_paras[idx]})
            elif op == "replace":
                for idx in range(i1, i2):
                    result.append({"type": "removed", "text": orig_paras[idx]})
                for idx in range(j1, j2):
                    result.append({"type": "added", "text": sugg_paras[idx]})
            elif op == "delete":
                for idx in range(i1, i2):
                    result.append({"type": "removed", "text": orig_paras[idx]})
            elif op == "insert":
                for idx in range(j1, j2):
                    result.append({"type": "added", "text": sugg_paras[idx]})

        return result

    def change_statistics(self, diffs: list[DiffLine]) -> dict[str, int]:
        """Compute change statistics from a list of diff lines."""
        stats = {"added": 0, "removed": 0, "changed": 0, "same": 0}
        for d in diffs:
            if d.type in stats:
                stats[d.type] += 1
        return stats
