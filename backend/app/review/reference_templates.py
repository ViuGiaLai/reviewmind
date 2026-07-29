from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from .models import BlockType, DocumentModel, Evidence, Issue, Severity
from .parser import FileParser


EMU_PER_INCH = 914400.0


def _round(value: float, digits: int = 2) -> float:
    return round(float(value or 0), digits)

def _clean_extracted_text(value: str) -> str:
    """Normalize a known DOCX parser artifact where run text is mirrored."""
    text = value.strip()
    middle = len(text) // 2
    if len(text) % 2 == 0 and text[:middle] == text[middle:]:
        return text[:middle].strip()
    return text


class ReferenceTemplateEngine:
    """Learn deterministic structure/format rules from a DOCX reference file."""

    def __init__(self) -> None:
        self.parser = FileParser()

    def learn(self, content: bytes, filename: str) -> dict[str, Any]:
        if not filename.casefold().endswith(".docx"):
            raise ValueError("Reference templates must be DOCX files.")
        document = self.parser.parse(
            content,
            filename,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        headings: dict[str, dict[str, Any]] = {}
        required_sections: list[str] = []
        for block in document.blocks:
            if block.type != BlockType.HEADING or not block.text.strip():
                continue
            key = str(block.level or 1)
            headings.setdefault(
                key,
                {
                    "level": block.level or 1,
                    "style_name": block.style_name,
                    "font_name": block.font_name,
                    "font_size": _round(block.font_size),
                    "bold": block.bold,
                    "alignment": block.alignment,
                },
            )
            title = _clean_extracted_text(block.text)
            if title.casefold() not in {item.casefold() for item in required_sections}:
                required_sections.append(title)

        metadata = document.metadata
        return {
            "version": 1,
            "source_filename": filename,
            "content_policy": "format_and_structure_only",
            "body_text_is_user_owned": True,
            "layout": {
                "page_width_in": _round(metadata.page_width / EMU_PER_INCH),
                "page_height_in": _round(metadata.page_height / EMU_PER_INCH),
                "margin_top_in": _round(metadata.margin_top / EMU_PER_INCH),
                "margin_bottom_in": _round(metadata.margin_bottom / EMU_PER_INCH),
                "margin_left_in": _round(metadata.margin_left / EMU_PER_INCH),
                "margin_right_in": _round(metadata.margin_right / EMU_PER_INCH),
            },
            "body": {
                "font_name": metadata.default_font,
                "font_size": _round(metadata.default_font_size),
                "line_spacing": _round(metadata.line_spacing),
            },
            "heading_styles": headings,
            "required_sections": required_sections,
            "signals": {
                "has_header": any(b.type == BlockType.HEADER for b in document.blocks),
                "has_footer": any(b.type == BlockType.FOOTER for b in document.blocks),
                "table_count": len(document.tables),
                "figure_count": len(document.figures),
            },
        }

    def compare(self, document: DocumentModel, template: dict[str, Any]) -> list[Issue]:
        """Compare only structure/format. Body wording is intentionally ignored."""
        issues: list[Issue] = []
        expected_layout = template.get("layout") or {}
        actual_layout = {
            "margin_top_in": document.metadata.margin_top / EMU_PER_INCH,
            "margin_bottom_in": document.metadata.margin_bottom / EMU_PER_INCH,
            "margin_left_in": document.metadata.margin_left / EMU_PER_INCH,
            "margin_right_in": document.metadata.margin_right / EMU_PER_INCH,
        }
        for key, label in (
            ("margin_top_in", "top"),
            ("margin_bottom_in", "bottom"),
            ("margin_left_in", "left"),
            ("margin_right_in", "right"),
        ):
            expected = float(expected_layout.get(key) or 0)
            actual = float(actual_layout.get(key) or 0)
            if expected and actual and abs(expected - actual) > 0.08:
                issues.append(self._issue(
                    "formatting", f"template.layout.{key}", Severity.MEDIUM,
                    f"Page {label} margin is {actual:.2f} in; the reference template uses {expected:.2f} in.",
                    f"Set the {label} margin to {expected:.2f} in.",
                ))

        expected_body = template.get("body") or {}
        if expected_body.get("font_name") and document.metadata.default_font:
            if expected_body["font_name"].casefold() != document.metadata.default_font.casefold():
                issues.append(self._issue(
                    "formatting", "template.body.font", Severity.MEDIUM,
                    f"Body font is {document.metadata.default_font}; the reference template uses {expected_body['font_name']}.",
                    f"Apply {expected_body['font_name']} to the Normal/body style.",
                ))
        expected_size = float(expected_body.get("font_size") or 0)
        if expected_size and document.metadata.default_font_size and abs(expected_size - document.metadata.default_font_size) > 0.25:
            issues.append(self._issue(
                "formatting", "template.body.font_size", Severity.LOW,
                f"Body font size is {document.metadata.default_font_size:g} pt; the reference template uses {expected_size:g} pt.",
                f"Set the Normal/body style to {expected_size:g} pt.",
            ))

        actual_sections = {text.strip().casefold() for _, text, _ in document.headings}
        # Rich DOCX headings are more reliable than TextParser's markdown-only headings.
        actual_sections.update(
            _clean_extracted_text(block.text).casefold()
            for block in document.blocks
            if block.type == BlockType.HEADING and block.text.strip()
        )
        for section in template.get("required_sections") or []:
            if section.strip().casefold() not in actual_sections:
                issues.append(self._issue(
                    "structure", "template.structure.missing_section", Severity.HIGH,
                    f'Required section "{section}" from the reference template is missing.',
                    f'Add the "{section}" section using the corresponding heading style.',
                ))
        return issues

    @staticmethod
    def _issue(category: str, rule_id: str, severity: Severity, message: str, recommendation: str) -> Issue:
        return Issue(
            id=str(uuid4()),
            category=category,
            rule_id=rule_id,
            severity=severity,
            message=message,
            recommendation=recommendation,
            evidence=Evidence(
                excerpt="Reference template comparison",
                line_start=1,
                line_end=1,
                location="Document formatting and structure",
            ),
            confidence=95,
            source="reference_template",
            autofix_allowed=False,
        )
