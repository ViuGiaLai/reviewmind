from __future__ import annotations

import re
from typing import Any


class SafeFixRules:
    """Collection of safe, deterministic fix rules that can be auto-applied."""

    # ── Heading Style ─────────────────────────────────────────────────────────
    @staticmethod
    def fix_heading_style(text: str) -> str:
        lines = text.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("##") and not stripped.startswith("## "):
                idx = stripped.index("##")
                rest = stripped[idx + 2:].strip()
                result.append(f"## {rest}" if rest else line)
            elif stripped.startswith("#") and not stripped.startswith("# "):
                idx = stripped.index("#")
                rest = stripped[idx + 1:].strip()
                result.append(f"# {rest}" if rest else line)
            else:
                result.append(line)
        return "\n".join(result)

    # ── Line Spacing ──────────────────────────────────────────────────────────
    @staticmethod
    def fix_line_spacing(text: str, target_spacing: int = 2) -> str:
        """Normalize excessive blank lines."""
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
        return text

    # ── Reference Formatting ──────────────────────────────────────────────────
    @staticmethod
    def fix_reference_formatting(text: str, style: str = "apa") -> str:
        if style == "apa":
            # Ensure DOI is lowercase
            text = re.sub(r"DOI:\s*", "doi:", text, flags=re.IGNORECASE)
            # Ensure hanging indent placeholders
            text = re.sub(r"^References\s*$", "References", text, flags=re.MULTILINE)
        elif style == "ieee":
            # Ensure IEEE bracket format [1], [2], etc.
            text = re.sub(r"\[(\d+)\]", lambda m: f"[{m.group(1)}]", text)
        return text

    # ── Broken Hyperlinks ─────────────────────────────────────────────────────
    @staticmethod
    def fix_http_prefix(text: str) -> str:
        """Fix common URL formatting issues."""
        text = re.sub(r"(?<!:)//", "://", text)
        text = re.sub(r"https?(?!!)", lambda m: m.group(0), text, flags=re.IGNORECASE)
        return text

    # ── Bullet List Consistency ───────────────────────────────────────────────
    @staticmethod
    def fix_bullet_consistency(text: str) -> str:
        lines = text.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            # Normalize inconsistent bullet characters
            if stripped.startswith("* ") or stripped.startswith("- "):
                indent = line[:len(line) - len(line.lstrip())]
                content = stripped[2:]
                result.append(f"{indent}- {content}")
            else:
                result.append(line)
        return "\n".join(result)

    # ── Punctuation (spacing after period) ────────────────────────────────────
    @staticmethod
    def fix_period_spacing(text: str) -> str:
        """Fix missing space after period."""
        text = re.sub(r"\.([A-Z])", r". \1", text)
        # Fix double space after period
        text = re.sub(r"\.  ", ". ", text)
        return text

    # ── Citation Order (IEEE style) ───────────────────────────────────────────
    @staticmethod
    def fix_citation_order(text: str) -> str:
        """Sort IEEE-style brackets in ascending order within a sentence."""
        def sort_brackets(m: re.Match) -> str:
            nums = re.findall(r"\d+", m.group(0))
            sorted_nums = sorted(int(n) for n in nums)
            return ", ".join(f"[{n}]" for n in sorted_nums) if len(sorted_nums) > 1 else f"[{sorted_nums[0]}]"

        text = re.sub(r"\[[\d,\s]+\]", sort_brackets, text)
        return text

    # ── Bullet List Capitalization ────────────────────────────────────────────
    @staticmethod
    def fix_bullet_capitalization(text: str) -> str:
        lines = text.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- ") and len(stripped) > 2:
                indent = line[:len(line) - len(line.lstrip())]
                content = stripped[0].upper() + stripped[1:]
                result.append(f"{indent}- {content[2:]}" if stripped[0].islower() else line)
            else:
                result.append(line)
        return "\n".join(result)
