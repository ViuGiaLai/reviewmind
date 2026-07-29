from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class PackCapability:
    """A capability provided by a knowledge pack."""
    id: str
    name: str
    description: str
    category: str
    severity: str = "medium"
    enabled: bool = True


@dataclass(frozen=True)
class PackPermission:
    """Permission overrides for a knowledge pack."""
    category: str
    detect: bool = True
    explain: bool = True
    suggest: bool = True
    rewrite: bool = False
    autofix: bool = False


@dataclass(frozen=True)
class KnowledgePack:
    """A knowledge pack that extends review capabilities."""
    id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    profile: str = ""
    author: str = ""
    website: str = ""
    categories: list[str] = field(default_factory=list)
    capabilities: list[PackCapability] = field(default_factory=list)
    permissions: list[PackPermission] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)  # Rule IDs this pack provides
    required_packs: list[str] = field(default_factory=list)
    incompatible_packs: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    prompts: dict[str, str] = field(default_factory=dict)
    rubrics: dict[str, Any] = field(default_factory=dict)
    checklists: list[str] = field(default_factory=list)


class PackLoader:
    """Loads and validates knowledge packs from config directory."""

    def __init__(self, config_directory: Path | None = None):
        self.config_directory = config_directory or (
            Path(__file__).resolve().parents[2] / "config" / "packs"
        )
        self._cache: dict[str, KnowledgePack] = {}

    def load(self, pack_id: str) -> KnowledgePack:
        """Load a single knowledge pack by ID."""
        if pack_id in self._cache:
            return self._cache[pack_id]

        path = self.config_directory / pack_id / "pack.yaml"
        if not path.is_file():
            raise ValueError(f"Knowledge pack not found: {pack_id}")

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        pack = self._parse_pack(data, pack_id)
        self._cache[pack_id] = pack
        return pack

    def load_all(self) -> list[KnowledgePack]:
        """Load all available knowledge packs."""
        packs = []
        for pack_dir in sorted(self.config_directory.glob("*/pack.yaml")):
            try:
                pack = self.load(pack_dir.parent.name)
                packs.append(pack)
            except (ValueError, yaml.YAMLError):
                pass
        return packs

    def get_for_profile(self, profile_id: str) -> list[KnowledgePack]:
        """Get all packs compatible with a given profile."""
        return [p for p in self.load_all() if p.profile == profile_id]

    def validate_compatibility(self, pack_ids: list[str]) -> list[str]:
        """Validate a set of packs for compatibility. Returns warnings."""
        warnings: list[str] = []
        packs = {}
        for pid in pack_ids:
            try:
                packs[pid] = self.load(pid)
            except ValueError:
                warnings.append(f"Pack '{pid}' not found.")

        # Check required packs
        for pid, pack in packs.items():
            for req in pack.required_packs:
                if req not in packs:
                    warnings.append(f"Pack '{pid}' requires '{req}' which is not selected.")

        # Check incompatible packs
        for pid, pack in packs.items():
            for inc in pack.incompatible_packs:
                if inc in packs:
                    warnings.append(f"Pack '{pid}' is incompatible with '{inc}'.")

        return warnings

    def get_capabilities(self, pack_ids: list[str]) -> list[dict[str, Any]]:
        """Get merged capabilities for a set of packs."""
        caps: list[dict[str, Any]] = []
        for pid in pack_ids:
            try:
                pack = self.load(pid)
                for cap in pack.capabilities:
                    caps.append({
                        "id": cap.id,
                        "name": cap.name,
                        "description": cap.description,
                        "category": cap.category,
                        "severity": cap.severity,
                        "pack": pack.name,
                        "enabled": cap.enabled,
                    })
            except ValueError:
                pass
        return caps

    def get_merged_permissions(
        self, profile_permissions: dict[str, int], pack_ids: list[str]
    ) -> dict[str, int]:
        """Merge profile permissions with pack-specific overrides."""
        result = dict(profile_permissions)

        for pid in pack_ids:
            try:
                pack = self.load(pid)
                for perm in pack.permissions:
                    level = 0
                    if perm.detect:
                        level = max(level, 1)
                    if perm.explain:
                        level = max(level, 2)
                    if perm.suggest:
                        level = max(level, 3)
                    if perm.rewrite:
                        level = max(level, 4)
                    if perm.autofix:
                        level = max(level, 5)

                    if perm.category in result:
                        result[perm.category] = max(result[perm.category], level)
                    else:
                        result[perm.category] = level
            except ValueError:
                pass

        return result

    def get_pack_rules(self, pack_ids: list[str]) -> list[str]:
        """Get all rules provided by a set of packs."""
        rules: list[str] = []
        for pid in pack_ids:
            try:
                pack = self.load(pid)
                rules.extend(pack.rules)
            except ValueError:
                pass
        return rules

    def get_pack_config(self, pack_ids: list[str]) -> dict[str, Any]:
        """Get merged config for a set of packs."""
        merged: dict[str, Any] = {}
        for pid in pack_ids:
            try:
                pack = self.load(pid)
                merged.update(pack.config)
            except ValueError:
                pass
        return merged

    def get_ai_context(self, pack_ids: list[str]) -> dict[str, Any]:
        """Return the Knowledge Pack material that is safe to place in AI prompts."""
        context: dict[str, Any] = {
            "names": [], "prompts": {}, "rubrics": {},
            "checklists": [], "capabilities": [],
        }
        for pack_id in pack_ids:
            try:
                pack = self.load(pack_id)
            except ValueError:
                continue
            context["names"].append(f"{pack.name} {pack.version}")
            context["prompts"].update(pack.prompts)
            context["rubrics"].update(pack.rubrics)
            context["checklists"].extend(pack.checklists)
            context["capabilities"].extend(
                {
                    "id": capability.id,
                    "category": capability.category,
                    "description": capability.description,
                }
                for capability in pack.capabilities
                if capability.enabled
            )
        return context

    def _parse_pack(self, data: dict[str, Any], pack_id: str) -> KnowledgePack:
        """Parse raw YAML data into a KnowledgePack object."""
        capabilities = [
            PackCapability(
                id=cap.get("id", f"{pack_id}-{i}"),
                name=cap.get("name", ""),
                description=cap.get("description", ""),
                category=cap.get("category", ""),
                severity=cap.get("severity", "medium"),
                enabled=cap.get("enabled", True),
            )
            for i, cap in enumerate(data.get("capabilities", []))
        ]

        permissions = [
            PackPermission(
                category=perm.get("category", ""),
                detect=perm.get("detect", True),
                explain=perm.get("explain", True),
                suggest=perm.get("suggest", True),
                rewrite=perm.get("rewrite", False),
                autofix=perm.get("autofix", False),
            )
            for perm in data.get("permissions", [])
        ]

        return KnowledgePack(
            id=data.get("id", pack_id),
            name=data.get("name", pack_id),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            profile=data.get("profile", ""),
            author=data.get("author", ""),
            website=data.get("website", ""),
            categories=data.get("categories", []),
            capabilities=capabilities,
            permissions=permissions,
            rules=data.get("rules", []),
            required_packs=data.get("required_packs", []),
            incompatible_packs=data.get("incompatible_packs", []),
            config=data.get("config", {}),
            prompts=data.get("prompts", {}),
            rubrics=data.get("rubrics", {}),
            checklists=data.get("checklists", []),
        )
