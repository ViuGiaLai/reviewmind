from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class Evidence:
    excerpt: str
    line_start: int
    line_end: int
    location: str


@dataclass(frozen=True)
class DocumentModel:
    filename: str
    content_type: str
    text: str
    lines: list[str]
    headings: list[tuple[int, str, int]]
    references: list[str]


@dataclass(frozen=True)
class Issue:
    id: str
    category: str
    rule_id: str
    severity: Severity
    message: str
    recommendation: str
    evidence: Evidence
    confidence: int
    source: str
    autofix_allowed: bool = False


@dataclass(frozen=True)
class ReviewRequest:
    text: str
    filename: str = "document.md"
    content_type: str = "text/markdown"
    profile_id: str = "academic"
    pack_ids: list[str] = field(default_factory=list)
    enabled_categories: list[str] | None = None


@dataclass(frozen=True)
class ReviewResult:
    profile_id: str
    pack_ids: list[str]
    issues: list[Issue]
    score: int
    category_scores: dict[str, int]
    summary: str
    report_markdown: str
