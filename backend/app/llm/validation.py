from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    """Result of validating a structured LLM response."""
    valid: bool
    parsed: Any = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class StructuredOutputValidator:
    """Validates and parses structured JSON output from LLM responses."""

    # Expected schemas for different response types
    ISSUE_SCHEMA = {
        "type": "object",
        "required": ["category", "rule_id", "severity", "message", "recommendation"],
        "properties": {
            "category": {"type": "string", "enum": ["structure", "writing", "citation", "format", "logic", "technical"]},
            "rule_id": {"type": "string", "pattern": r"^[a-z]+\.[a-z0-9_-]+$"},
            "severity": {"type": "string", "enum": ["high", "medium", "low"]},
            "message": {"type": "string", "min_length": 5},
            "recommendation": {"type": "string", "min_length": 5},
            "evidence_excerpt": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 100},
        },
    }

    FIX_SCHEMA = {
        "type": "object",
        "required": ["original", "suggested"],
        "properties": {
            "original": {"type": "string", "min_length": 1},
            "suggested": {"type": "string", "min_length": 1},
            "explanation": {"type": "string"},
        },
    }

    def extract_json(self, text: str) -> list[dict[str, Any]]:
        """Extract JSON array/object from LLM response text."""
        results = []

        # Try to find JSON in code blocks
        json_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text)
        for block in json_blocks:
            parsed = self._parse_json_block(block)
            if parsed is not None:
                results.extend(parsed if isinstance(parsed, list) else [parsed])

        if results:
            return results

        # Try to find JSON array directly
        array_match = re.search(r"\[[\s\S]*\]", text)
        if array_match:
            parsed = self._parse_json_block(array_match.group())
            if parsed and isinstance(parsed, list):
                return parsed

        # Try to find JSON object directly
        obj_match = re.search(r"\{[\s\S]*\}", text)
        if obj_match:
            parsed = self._parse_json_block(obj_match.group())
            if parsed:
                # Handle {"issues": [...]} format — unwrap the issues array
                if isinstance(parsed, dict) and "issues" in parsed:
                    issues_list = parsed["issues"]
                    if isinstance(issues_list, list):
                        return issues_list
                return [parsed] if isinstance(parsed, dict) else parsed

        return []

    def _parse_json_block(self, text: str) -> Any:
        """Try to parse a JSON string."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try fixing common issues
        text = text.strip()
        # Remove trailing commas
        text = re.sub(r",\s*([}\]])", r"\1", text)
        # Fix single quotes
        text = text.replace("'", '"')
        # Fix unquoted keys
        text = re.sub(r"(\s+)(\w+)(\s*):", r'\1"\2"\3:', text)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def validate_issues(self, data: list[dict[str, Any]]) -> ValidationResult:
        """Validate a list of issue objects."""
        result = ValidationResult(valid=True, parsed=[])

        for i, item in enumerate(data):
            if not isinstance(item, dict):
                result.errors.append(f"Item {i}: expected object, got {type(item).__name__}")
                continue

            # Check required fields
            missing = [f for f in self.ISSUE_SCHEMA["required"] if f not in item]
            if missing:
                result.errors.append(f"Item {i}: missing required fields: {', '.join(missing)}")
                continue

            # Validate severity
            if item.get("severity") not in ("high", "medium", "low"):
                result.warnings.append(f"Item {i}: invalid severity '{item.get('severity')}', defaulting to 'medium'")
                item["severity"] = "medium"

            # Validate confidence
            conf = item.get("confidence", 50)
            if not isinstance(conf, (int, float)) or conf < 0 or conf > 100:
                result.warnings.append(f"Item {i}: invalid confidence {conf}, defaulting to 50")
                item["confidence"] = 50

            # Ensure evidence_excerpt exists
            if "evidence_excerpt" not in item:
                item["evidence_excerpt"] = ""

            result.parsed.append(item)

        if result.errors:
            result.valid = False
        elif result.warnings:
            # Warnings are non-fatal
            pass

        return result

    def validate_fix(self, data: dict[str, Any]) -> ValidationResult:
        """Validate a single fix suggestion."""
        result = ValidationResult(valid=True, parsed=data)

        if not isinstance(data, dict):
            result.errors.append(f"Expected object, got {type(data).__name__}")
            result.valid = False
            return result

        if "original" not in data or "suggested" not in data:
            result.errors.append("Missing required fields: original, suggested")
            result.valid = False
            return result

        if not data["original"] or not data["suggested"]:
            result.errors.append("Original and suggested text must not be empty")
            result.valid = False
            return result

        if data["original"] == data["suggested"]:
            result.warnings.append("Original and suggested text are identical")

        return result

    def sanitize_response(self, text: str, max_length: int = 100000) -> str:
        """Sanitize and truncate LLM response."""
        # Remove null bytes
        text = text.replace("\x00", "")
        # Remove control characters (except newlines and tabs)
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)
        # Truncate
        if len(text) > max_length:
            text = text[:max_length] + "\n\n[...response truncated...]"
        return text


# Global instance
validator = StructuredOutputValidator()
