from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import threading
from typing import Any

import yaml


DEFAULT_PROFILES = {
    "academic": "academic",
    "business": "business",
    "sop": "sop",
    "technical_design": "technical_design",
    "research": "research",
    "legal": "legal",
    "general": "general",
}


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    categories: list[str]
    weights: dict[str, int]
    permissions: dict[str, int]
    required_sections: list[str]
    description: str = ""
    document_types: list[str] = field(default_factory=list)
    forbidden_sections: list[str] = field(default_factory=list)
    rubric: dict[str, str] = field(default_factory=dict)
    ai_focus: list[str] = field(default_factory=list)
    auto_fix_policy: dict[str, str] = field(default_factory=dict)


class ProfileLoader:
    def __init__(self, config_directory: Path):
        self.config_directory = config_directory
        self._cache: dict[str, tuple[int, Profile]] = {}
        self._cache_lock = threading.Lock()

    def load(self, profile_id: str) -> Profile:
        if profile_id == "auto":
            profile_id = self.detect_profile_from_text("")

        normalized = (profile_id or "academic").strip().casefold()
        profile_key = DEFAULT_PROFILES.get(normalized, normalized)
        path = self.config_directory / "profiles" / f"{profile_key}.yaml"
        if not path.is_file():
            raise ValueError(f"Unknown profile: {profile_id}")
        mtime = path.stat().st_mtime_ns
        with self._cache_lock:
            cached = self._cache.get(profile_key)
            if cached and cached[0] == mtime:
                return cached[1]
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        profile = Profile(
            id=data["id"],
            name=data["name"],
            categories=data.get("categories", []),
            description=data.get("description", ""),
            weights=data.get("weights", {}),
            permissions=data.get("permissions", {}),
            required_sections=data.get("required_sections", []),
            document_types=data.get("document_types", []),
            forbidden_sections=data.get("forbidden_sections", []),
            rubric=data.get("rubric", {}),
            ai_focus=data.get("ai_focus", []),
            auto_fix_policy=data.get("auto_fix_policy", {}),
        )
        with self._cache_lock:
            self._cache[profile_key] = (mtime, profile)
        return profile

    def detect_profile_from_text(self, text: str, filename: str = "", headings: list[str] = None) -> str:
        from ..document_type import DocumentTypeDetector

        detector = DocumentTypeDetector()
        result = detector.detect(headings=headings, text=text, filename=filename)
        return result.profile_id

    def available(self) -> list[dict[str, Any]]:
        profiles: list[dict[str, Any]] = []
        for path in sorted((self.config_directory / "profiles").glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            profiles.append({
                "id": data.get("id", path.stem),
                "name": data.get("name", path.stem),
                "description": data.get("description", ""),
                "document_types": data.get("document_types", []),
                "categories": data.get("categories", []),
            })
        return profiles
