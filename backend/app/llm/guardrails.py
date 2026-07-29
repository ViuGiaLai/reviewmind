from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.config import settings


@dataclass
class GuardrailResult:
    """Result of a guardrail check."""
    allowed: bool
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    redacted_text: str = ""


class SafetyGuardrails:
    """Enforces safety policies for AI review: SOP compliance, PII, data handling."""

    # ── PII Patterns ──────────────────────────────────────────────────────

    PII_PATTERNS = {
        "email": re.compile(r"\b[\w._%+-]+@[\w.-]+\.[a-zA-Z]{2,}\b"),
        "phone": re.compile(r"\b(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
        "api_key_like": re.compile(r"\b(sk-[a-zA-Z0-9]{20,}|[A-Za-z0-9]{32,})\b"),
    }

    # ── SOP/Compliance Restricted Actions ─────────────────────────────────

    SOP_RESTRICTED_ACTIONS = {
        "rewrite": {
            "keywords": ["rewrite", "rephrase", "paraphrase", "change the meaning"],
            "severity": "high",
            "reason": "SOP documents must not be rephrased. Only formatting fixes allowed.",
        },
        "delete_required": {
            "keywords": ["remove", "delete required section", "omit"],
            "severity": "high",
            "reason": "Required compliance sections must not be removed.",
        },
        "change_terminology": {
            "keywords": ["change terminology", "replace technical term", "simplify language"],
            "severity": "medium",
            "reason": "Technical terminology changes require regulatory approval.",
        },
    }

    # ── Sensitive Data Patterns ───────────────────────────────────────────

    SENSITIVE_TOPICS = [
        "trade secret", "confidential", "classified", "proprietary",
        "internal only", "do not distribute", "embargoed",
    ]

    def __init__(self):
        self.config = settings.llm

    def check_input(
        self,
        text: str,
        profile_id: str = "",
        check_pii: bool = True,
        check_sensitive: bool = True,
    ) -> GuardrailResult:
        """Check input text before sending to LLM provider."""
        details: dict[str, Any] = {}

        # Check PII
        if check_pii:
            pii_found = self._detect_pii(text)
            if pii_found:
                if not self.config.allow_sensitive_data:
                    redacted = self._redact_pii(text, pii_found)
                    return GuardrailResult(
                        allowed=False,
                        reason=f"PII detected: {', '.join(pii_found.keys())}. "
                               f"Set REVIEWMIND_ALLOW_SENSITIVE_DATA=true or redact the data.",
                        details={"pii_found": pii_found},
                        redacted_text=redacted,
                    )
                details["pii_redacted"] = list(pii_found.keys())

        # Check sensitive topics
        if check_sensitive:
            sensitive_found = self._detect_sensitive(text)
            if sensitive_found:
                details["sensitive_topics"] = sensitive_found

        return GuardrailResult(allowed=True, details=details)

    def check_output(
        self,
        text: str,
        profile_id: str = "",
        check_rephrase: bool = True,
    ) -> GuardrailResult:
        """Check LLM output against safety policies."""
        details: dict[str, Any] = {}
        text_lower = text.lower()

        # SOP check: detect restricted actions in suggestions
        if profile_id == "sop" and check_rephrase:
            for action_name, rule in self.SOP_RESTRICTED_ACTIONS.items():
                found = [kw for kw in rule["keywords"] if kw in text_lower]
                if found:
                    details[action_name] = {
                        "keywords_found": found,
                        "severity": rule["severity"],
                    }
                    if rule["severity"] == "high":
                        return GuardrailResult(
                            allowed=False,
                            reason=rule["reason"],
                            details=details,
                        )

        return GuardrailResult(allowed=True, details=details)

    def _detect_pii(self, text: str) -> dict[str, list[str]]:
        """Detect PII in text, returning type -> matches mapping."""
        found: dict[str, list[str]] = {}
        for name, pattern in self.PII_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                found[name] = list(set(matches))[:5]  # Max 5 per type
        return found

    def _redact_pii(self, text: str, pii_found: dict[str, list[str]]) -> str:
        """Redact PII from text."""
        redacted = text
        for name, matches in pii_found.items():
            for m in matches:
                redacted = redacted.replace(m, f"[REDACTED_{name.upper()}]")
        return redacted

    def _detect_sensitive(self, text: str) -> list[str]:
        """Detect sensitive content markers."""
        text_lower = text.lower()
        return [t for t in self.SENSITIVE_TOPICS if t in text_lower]

    def validate_review_request(
        self,
        provider_name: str,
        profile_id: str,
        document_text: str,
    ) -> GuardrailResult:
        """Full validation before sending document to LLM provider."""
        checks = []

        # 1. Input guardrails
        input_check = self.check_input(document_text, profile_id)
        if not input_check.allowed:
            return input_check
        checks.append(input_check)

        # 2. Profile-specific restrictions
        if profile_id == "sop":
            # SOP: additional restrictions
            checks.append(GuardrailResult(
                allowed=True,
                reason="SOP review restricted to formatting and consistency checks only.",
                details={"profile_restricted": "sop_no_content_rewrite"},
            ))

        # 3. Data retention policy (check cleanup_days from app settings)
        if not self.config.allow_sensitive_data and settings.app.cleanup_days < 1:
            return GuardrailResult(
                allowed=False,
                reason="Data retention policy requires at least 1 day. Set REVIEWMIND_CLEANUP_DAYS.",
            )

        return GuardrailResult(allowed=True, details={})

    def get_restricted_profiles(self) -> list[str]:
        """Return list of profiles with restricted AI operations."""
        return ["sop"]  # SOP cannot be rewritten by AI


# Global instance
guardrails = SafetyGuardrails()
