"""Rule configuration manager: category enable/disable, severity override, ignore lists, custom thresholds."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import Severity


@dataclass
class RuleOverride:
    """Per-rule configuration override."""
    enabled: bool | None = None
    severity: Severity | None = None
    priority: int | None = None
    confidence: int | None = None
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class CategoryConfig:
    """Per-category configuration."""
    enabled: bool = True
    severity_override: Severity | None = None
    rules: dict[str, RuleOverride] = field(default_factory=dict)


@dataclass
class RuleConfiguration:
    """Complete rule configuration for a review session."""
    # Category-level toggles
    categories: dict[str, CategoryConfig] = field(default_factory=dict)

    # Global ignore list (rule IDs)
    disabled_rules: set[str] = field(default_factory=set)

    # Profile-specific overrides
    profile_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Pack-specific overrides
    pack_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Custom thresholds (applied to all rules)
    custom_thresholds: dict[str, Any] = field(default_factory=dict)

    # Category weights for scoring
    category_weights: dict[str, float] = field(default_factory=dict)

    def is_category_enabled(self, category: str) -> bool:
        """Check if a category is enabled."""
        if category in self.categories:
            return self.categories[category].enabled
        return True

    def is_rule_enabled(self, rule_id: str) -> bool:
        """Check if a rule is enabled."""
        if rule_id in self.disabled_rules:
            return False
        # Check category-level disable
        category = rule_id.split(".")[0]
        if category and not self.is_category_enabled(category):
            return False
        return True

    def get_rule_override(self, category: str, rule_id: str) -> RuleOverride | None:
        """Get override for a specific rule."""
        cat_config = self.categories.get(category)
        if cat_config:
            return cat_config.rules.get(rule_id)
        return None

    def get_category_severity(self, category: str) -> Severity | None:
        """Get severity override for a category."""
        cat_config = self.categories.get(category)
        if cat_config:
            return cat_config.severity_override
        return None

    def disable_category(self, category: str) -> None:
        """Disable an entire category."""
        if category not in self.categories:
            self.categories[category] = CategoryConfig(enabled=False)
        else:
            self.categories[category].enabled = False

    def enable_category(self, category: str) -> None:
        """Enable an entire category."""
        if category not in self.categories:
            self.categories[category] = CategoryConfig(enabled=True)
        else:
            self.categories[category].enabled = True

    def disable_rule(self, rule_id: str) -> None:
        """Disable a specific rule."""
        self.disabled_rules.add(rule_id)

    def enable_rule(self, rule_id: str) -> None:
        """Enable a specific rule."""
        self.disabled_rules.discard(rule_id)

    def set_category_weight(self, category: str, weight: float) -> None:
        """Set scoring weight for a category."""
        self.category_weights[category] = weight

    def set_rule_config(self, category: str, rule_id: str, **config: Any) -> None:
        """Set configuration for a specific rule."""
        if category not in self.categories:
            self.categories[category] = CategoryConfig()
        cat = self.categories[category]
        if rule_id not in cat.rules:
            cat.rules[rule_id] = RuleOverride()
        cat.rules[rule_id].config.update(config)

    def set_custom_threshold(self, key: str, value: Any) -> None:
        """Set a global custom threshold."""
        self.custom_thresholds[key] = value

    def get_applied_config(
        self,
        category: str,
        rule_id: str,
        base_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Get the final configuration for a rule, merging all overrides."""
        config = dict(base_config)

        # Apply custom thresholds
        config.update(self.custom_thresholds)

        # Apply rule override config
        override = self.get_rule_override(category, rule_id)
        if override:
            config.update(override.config)

        return config

    def to_dict(self) -> dict[str, Any]:
        """Serialize configuration for API responses."""
        return {
            "categories": {
                cat: {
                    "enabled": cfg.enabled,
                    "severity_override": cfg.severity_override.value if cfg.severity_override else None,
                    "rules_disabled": sum(1 for r in cfg.rules.values() if r.enabled is False),
                }
                for cat, cfg in self.categories.items()
            },
            "disabled_rules": list(self.disabled_rules),
            "category_weights": self.category_weights,
            "custom_thresholds": self.custom_thresholds,
        }
