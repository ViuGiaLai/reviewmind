from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DiffResult:
    """Result of comparing original and patched text."""
    original: str
    patched: str
    unified_diff: str
    has_changes: bool
    change_count: int
    additions: list[str] = field(default_factory=list)
    deletions: list[str] = field(default_factory=list)


class DiffGenerator:
    """Generates unified and side-by-side diffs between original and patched text."""

    def generate_diff(
        self,
        original: str,
        patched: str,
        context_lines: int = 3,
    ) -> DiffResult:
        """Generate a unified diff between *original* and *patched* text."""
        orig_lines = original.splitlines(keepends=True)
        patch_lines = patched.splitlines(keepends=True)

        diff_lines = list(
            difflib.unified_diff(
                orig_lines,
                patch_lines,
                fromfile="original",
                tofile="fixed",
                n=context_lines,
            )
        )

        unified_diff = "".join(diff_lines)
        additions = [ln for ln in diff_lines if ln.startswith("+") and not ln.startswith("++")]
        deletions = [ln for ln in diff_lines if ln.startswith("-") and not ln.startswith("--")]

        return DiffResult(
            original=original,
            patched=patched,
            unified_diff=unified_diff,
            has_changes=bool(diff_lines),
            change_count=len(additions) + len(deletions),
            additions=additions,
            deletions=deletions,
        )

    def generate_side_by_side(
        self,
        original: str,
        patched: str,
    ) -> list[dict[str, Any]]:
        """Generate a side-by-side diff suitable for UI display.

        Returns a list of row dicts with keys ``type``, ``left``, and ``right``.
        *type* is one of ``"equal"``, ``"replace"``, ``"delete"``, ``"insert"``.
        """
        orig_lines = original.splitlines()
        patch_lines = patched.splitlines()
        result: list[dict[str, Any]] = []

        matcher = difflib.SequenceMatcher(None, orig_lines, patch_lines)
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "equal":
                for i in range(i2 - i1):
                    result.append(
                        {
                            "type": "equal",
                            "left": orig_lines[i1 + i],
                            "right": patch_lines[j1 + i],
                        }
                    )
            elif op == "replace":
                for k in range(max(i2 - i1, j2 - j1)):
                    left = orig_lines[i1 + k] if i1 + k < i2 else ""
                    right = patch_lines[j1 + k] if j1 + k < j2 else ""
                    result.append({"type": "replace", "left": left, "right": right})
            elif op == "delete":
                for i in range(i1, i2):
                    result.append({"type": "delete", "left": orig_lines[i], "right": ""})
            elif op == "insert":
                for j in range(j1, j2):
                    result.append({"type": "insert", "left": "", "right": patch_lines[j]})

        return result
