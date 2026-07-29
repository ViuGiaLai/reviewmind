from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class IssueCategory(str, Enum):
    FORMATTING = "formatting"
    STRUCTURE = "structure"
    WRITING = "writing"
    CITATION = "citation"
    LOGIC = "logic"
    COMPLIANCE = "compliance"
    FIGURES = "figures"
    TABLES = "tables"
    CONSISTENCY = "consistency"
    AI_FINDING = "ai_finding"


class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueSource(str, Enum):
    RULE_ENGINE = "rule"
    AI_REVIEW = "ai"
    CROSS_RULE = "cross_rule"
    COMPLIANCE = "compliance"


class AutoFixCapability(str, Enum):
    SAFE = "safe"          # Can auto-fix without user review
    ASSISTED = "assisted"  # Auto-fix but user confirms
    AI_FIX = "ai_fix"     # AI generates fix, user confirms
    MANUAL = "manual"      # Cannot auto-fix


class ReadinessLevel(str, Enum):
    DRAFT = "draft"
    REVIEW_NEEDED = "review_needed"
    ALMOST_READY = "almost_ready"
    READY = "ready"


@dataclass
class UnifiedIssue:
    """The Unified Issue Model from PDS Chapter 9."""

    id: str = field(default_factory=lambda: str(uuid4()))
    category: IssueCategory = IssueCategory.WRITING
    source: IssueSource = IssueSource.RULE_ENGINE
    severity: IssueSeverity = IssueSeverity.MEDIUM
    confidence: float = 1.0  # 0.0 - 1.0
    title: str = ""
    description: str = ""
    evidence: str = ""
    expected: str = ""
    actual: str = ""
    recommendation: str = ""
    auto_fix_capability: AutoFixCapability = AutoFixCapability.MANUAL
    location: dict[str, Any] = field(default_factory=dict)  # page, section, line
    related_objects: list[str] = field(default_factory=list)  # node_ids
    knowledge_pack: str = ""
    rule_id: str = ""
    dependencies: list[str] = field(default_factory=list)  # IDs of issues this depends on
    is_duplicate: bool = False
    duplicate_of: str = ""
