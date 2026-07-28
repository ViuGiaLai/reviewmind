from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


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
        path = self.config_directory / "profiles" / f"{profile_id}.yaml"
        if not path.is_file():
            raise ValueError(f"Unknown profile: {profile_id}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return Profile(
            id=data["id"], name=data["name"], categories=data["categories"],
            weights=data["weights"], permissions=data["permissions"],
            required_sections=data.get("required_sections", []),
        )

    def available(self) -> list[dict[str, str]]:
        return [
            {"id": path.stem, "name": yaml.safe_load(path.read_text(encoding="utf-8"))["name"]}
            for path in sorted((self.config_directory / "profiles").glob("*.yaml"))
        ]
