from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


DEFAULT_PROFILES = {
    "academic": "academic",
    "business": "business",
    "sop": "sop",
    "technical_design": "technical_design",
}


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    categories: list[str]
    weights: dict[str, int]
    permissions: dict[str, int]
    required_sections: list[str]


class ProfileLoader:
    def __init__(self, config_directory: Path):
        self.config_directory = config_directory

    def load(self, profile_id: str) -> Profile:
        if profile_id == "auto":
            profile_id = self.detect_profile_from_text("")

        normalized = (profile_id or "academic").strip().casefold()
        profile_key = DEFAULT_PROFILES.get(normalized, normalized)
        path = self.config_directory / "profiles" / f"{profile_key}.yaml"
        if not path.is_file():
            raise ValueError(f"Unknown profile: {profile_id}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return Profile(
            id=data["id"], name=data["name"], categories=data["categories"],
            weights=data["weights"], permissions=data["permissions"],
            required_sections=data.get("required_sections", []),
        )

    def detect_profile_from_text(self, text: str) -> str:
        lowered = text.casefold()
        if any(token in lowered for token in ("architecture", "component", "configuration", "yaml", "pipeline", "design")):
            return "technical_design"
        if any(token in lowered for token in ("abstract", "introduction", "references", "bibliography", "methodology")):
            return "academic"
        if any(token in lowered for token in ("executive summary", "proposal", "budget", "timeline")):
            return "business"
        if any(token in lowered for token in ("procedure", "revision history", "safety", "compliance")):
            return "sop"
        return "academic"

    def available(self) -> list[dict[str, str]]:
        return [
            {"id": path.stem, "name": yaml.safe_load(path.read_text(encoding="utf-8"))["name"]}
            for path in sorted((self.config_directory / "profiles").glob("*.yaml"))
        ]
