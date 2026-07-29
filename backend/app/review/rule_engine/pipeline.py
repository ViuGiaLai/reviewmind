"""Rule pipeline: orchestrates all registered rules via the registry."""

from __future__ import annotations

from typing import Any, Callable

from ..models import DocumentModel, Issue
from ..profiles import Profile
from .config_manager import RuleConfiguration
from .registry import registry

# Import rule modules so they register themselves
from . import citation_rules  # noqa: F401
from . import format_rules  # noqa: F401
from . import writing_rules  # noqa: F401
from . import logic_rules  # noqa: F401
from . import structure_rules  # noqa: F401
from . import figure_table_rules  # noqa: F401
from . import compliance_rules  # noqa: F401

# Also keep old rules registered for backward compatibility
from . import legacy_rules  # noqa: F401


class RulePipeline:
    """Orchestrates all registered rules via the central registry."""

    def __init__(self, enable_parallel: bool = False):
        self.registry = registry
        self.enable_parallel = enable_parallel

    def run(
        self,
        document: DocumentModel,
        profile: Profile,
        categories: set[str],
        pack_ids: list[str] | None = None,
        config_overrides: dict[str, dict[str, object]] | None = None,
        rule_config: RuleConfiguration | None = None,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> list[Issue]:
        """Run all matching rules with optional config and progress."""
        # Resolve disabled rules from config
        disabled_rules: set[str] = set()
        merged_overrides: dict[str, dict[str, Any]] = dict(config_overrides or {})

        if rule_config:
            disabled_rules = set(rule_config.disabled_rules)
            # Also disable rules in disabled categories
            for cat, cfg in rule_config.categories.items():
                if not cfg.enabled:
                    for rid in self.registry.get_rule_ids_by_category(cat):
                        disabled_rules.add(rid)

        return self.registry.run_rules(
            document=document,
            profile=profile,
            categories=categories,
            pack_ids=pack_ids,
            config_overrides=merged_overrides,
            disabled_rules=disabled_rules,
            progress_callback=progress_callback,
        )

    def get_available_categories(self) -> set[str]:
        """Get all categories with registered rules."""
        return self.registry.get_categories()

    def get_rule_count_by_category(self) -> dict[str, int]:
        """Get rule counts per category."""
        return self.registry.count_by_category()

    def get_rules_for_pack(self, pack_id: str) -> list[dict[str, object]]:
        """Get rules provided by a specific knowledge pack."""
        rules = self.registry.list_rules(pack_id=pack_id)
        return [
            {
                "id": r.meta.id,
                "name": r.meta.name,
                "category": r.meta.category,
                "description": r.meta.description,
                "severity": r.meta.severity.value,
                "priority": r.meta.priority,
            }
            for r in rules
        ]
