from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from ..models import DocumentModel, Evidence, Issue, Severity
from ..profiles import Profile

logger = logging.getLogger(__name__)


# ─── Rule Definition ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RuleMeta:
    """Metadata for a registered rule."""
    id: str
    category: str
    name: str
    description: str
    severity: Severity
    priority: int = 0  # Higher = runs first
    confidence: int = 90
    source: str = "syntax-rule"
    autofix_allowed: bool = False
    pack_id: str = ""  # Which knowledge pack this belongs to (empty = core)
    pack_version: str = ""  # Version of pack that provides this rule
    depends_on: list[str] = field(default_factory=list)
    timeout_ms: int = 5000
    enabled_by_default: bool = True
    version: str = "1.0.0"  # Rule version for migration tracking
    tags: list[str] = field(default_factory=list)  # e.g., ["format", "apa", "essential"]


RuleFn = Callable[[DocumentModel, Profile, dict[str, Any]], list[Issue]]


@dataclass
class RegisteredRule:
    """A registered rule with its metadata and implementation."""
    meta: RuleMeta
    fn: RuleFn
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleResult:
    """Result of executing a single rule."""
    rule_id: str
    issues: list[Issue]
    execution_time_ms: float
    success: bool
    error: str | None = None
    version: str = "1.0.0"


@dataclass
class RuleStats:
    """Statistics for a rule across executions."""
    rule_id: str
    total_runs: int = 0
    total_issues: int = 0
    total_time_ms: float = 0.0
    avg_time_ms: float = 0.0
    error_count: int = 0
    last_run: float = 0.0


# ─── Rule Registry ────────────────────────────────────────────────────────────

class RuleRegistry:
    """Central registry for all rules with advanced execution features."""

    def __init__(self, enable_parallel: bool = False, max_workers: int = 4):
        self._rules: dict[str, RegisteredRule] = {}
        self._stats: dict[str, RuleStats] = {}
        self._cache: dict[str, tuple[float, list[Issue]]] = {}  # rule_id -> (timestamp, issues)
        self._cache_ttl: float = 30.0  # seconds
        self._rule_overrides: dict[str, dict[str, Any]] = {}  # rule_id -> override dict
        self.enable_parallel = enable_parallel
        self._executor = ThreadPoolExecutor(max_workers=max_workers) if enable_parallel else None

    # ── Registration ──────────────────────────────────────────────────────

    def register(self, rule_id: str, meta: RuleMeta, fn: RuleFn,
                 config: dict[str, Any] | None = None) -> None:
        """Register a rule with its metadata and implementation."""
        if rule_id in self._rules:
            logger.warning(f"Rule '{rule_id}' already registered — overwriting.")
        self._rules[rule_id] = RegisteredRule(meta=meta, fn=fn, config=config or {})
        self._stats[rule_id] = RuleStats(rule_id=rule_id)

    def unregister(self, rule_id: str) -> None:
        """Remove a registered rule."""
        self._rules.pop(rule_id, None)
        self._stats.pop(rule_id, None)
        self._cache.pop(rule_id, None)

    def get(self, rule_id: str) -> RegisteredRule | None:
        return self._rules.get(rule_id)

    def is_registered(self, rule_id: str) -> bool:
        return rule_id in self._rules

    # ── Listing & Filtering ───────────────────────────────────────────────

    def list_rules(
        self,
        categories: set[str] | None = None,
        pack_id: str | None = None,
        min_priority: int | None = None,
        tags: set[str] | None = None,
        enabled_only: bool = False,
    ) -> list[RegisteredRule]:
        """List rules with advanced filtering."""
        results = list(self._rules.values())
        if categories:
            results = [r for r in results if r.meta.category in categories]
        if pack_id is not None:
            results = [r for r in results if r.meta.pack_id == pack_id]
        if min_priority is not None:
            results = [r for r in results if r.meta.priority >= min_priority]
        if tags:
            results = [r for r in results if tags & set(r.meta.tags)]
        if enabled_only:
            results = [r for r in results if r.meta.enabled_by_default]
        results.sort(key=lambda r: (-r.meta.priority, r.meta.id))
        return results

    def get_categories(self) -> set[str]:
        """Get all unique category names."""
        return {r.meta.category for r in self._rules.values()}

    def count_by_category(self) -> dict[str, int]:
        """Count rules per category."""
        counts: dict[str, int] = {}
        for r in self._rules.values():
            counts[r.meta.category] = counts.get(r.meta.category, 0) + 1
        return counts

    def get_rules_for_pack(self, pack_id: str) -> list[dict[str, Any]]:
        """Get metadata for rules belonging to a pack."""
        rules = self.list_rules(pack_id=pack_id)
        return [
            {
                "id": r.meta.id,
                "name": r.meta.name,
                "category": r.meta.category,
                "description": r.meta.description,
                "severity": r.meta.severity.value,
                "priority": r.meta.priority,
                "version": r.meta.version,
                "tags": r.meta.tags,
            }
            for r in rules
        ]

    def get_rule_ids_by_category(self, category: str) -> list[str]:
        """Get all rule IDs for a given category (public API for pipeline/config)."""
        return [r_id for r_id, r in self._rules.items() if r.meta.category == category]

    # ── Dependency Resolution ─────────────────────────────────────────────

    def _resolve_dependencies(
        self, rules: list[RegisteredRule]
    ) -> list[list[RegisteredRule]]:
        """Topological sort with cycle detection. Returns batches (parallel-safe)."""
        # Build dependency graph
        all_ids = {r.meta.id for r in rules}
        deps: dict[str, set[str]] = {}
        for r in rules:
            deps[r.meta.id] = set(r.meta.depends_on) & all_ids

        # Topological sort (Kahn's algorithm)
        in_degree: dict[str, int] = {rid: 0 for rid in deps}
        for rid, dep_set in deps.items():
            for _dep in dep_set:
                in_degree[rid] = in_degree.get(rid, 0) + 1

        queue = [rid for rid, deg in in_degree.items() if deg == 0]
        sorted_ids: list[str] = []

        while queue:
            rid = queue.pop(0)
            sorted_ids.append(rid)
            for other_rid, dep_set in deps.items():
                if rid in dep_set:
                    in_degree[other_rid] -= 1
                    if in_degree[other_rid] == 0:
                        queue.append(other_rid)

        # Check for cycles
        if len(sorted_ids) != len(rules):
            cycle_ids = set(all_ids) - set(sorted_ids)
            logger.warning(f"Cycle detected in rule dependencies: {cycle_ids}")
            # Add remaining rules anyway
            sorted_ids.extend(cycle_ids)

        # Group into batches (same-priority rules can run in parallel)
        rule_map = {r.meta.id: r for r in rules}
        grouped: dict[int, list[RegisteredRule]] = {}
        for rid in sorted_ids:
            r = rule_map[rid]
            grouped.setdefault(r.meta.priority, []).append(r)

        # Return batches sorted by priority descending
        return [grouped[k] for k in sorted(grouped.keys(), reverse=True)]

    # ── Cache ─────────────────────────────────────────────────────────────

    def invalidate_cache(self, rule_id: str | None = None) -> None:
        """Invalidate rule cache."""
        if rule_id:
            self._cache.pop(rule_id, None)
        else:
            self._cache.clear()

    # ── Execution ─────────────────────────────────────────────────────────

    def run_rules(
        self,
        document: DocumentModel,
        profile: Profile,
        categories: set[str],
        pack_ids: list[str] | None = None,
        config_overrides: dict[str, dict[str, Any]] | None = None,
        disabled_rules: set[str] | None = None,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> list[Issue]:
        """Run all matching rules with dependency resolution, caching, and progress."""
        raw_rules = self.list_rules(categories=categories)
        config_overrides = config_overrides or {}
        disabled_rules = disabled_rules or set()
        issues: list[Issue] = []

        # Filter applicable rules
        applicable: list[RegisteredRule] = []
        for rule in raw_rules:
            # Skip disabled
            if rule.meta.id in disabled_rules:
                continue
            # Skip pack-specific if pack not selected
            if rule.meta.pack_id and pack_ids and rule.meta.pack_id not in pack_ids:
                continue
            if not rule.meta.enabled_by_default:
                continue
            applicable.append(rule)

        if not applicable:
            return issues

        # Resolve dependencies → batches
        batches = self._resolve_dependencies(applicable)
        total_batches = len(batches)

        for batch_idx, batch in enumerate(batches):
            if self.enable_parallel and len(batch) > 1:
                # Parallel execution within batch
                futures = []
                for rule in batch:
                    rule_config = dict(rule.config)
                    if rule.meta.id in config_overrides:
                        rule_config.update(config_overrides[rule.meta.id])
                    futures.append(self._executor.submit(
                        self._run_single_rule, rule, document, profile, rule_config
                    ))
                for future in futures:
                    result = future.result()
                    self._update_stats(result)
                    issues.extend(result.issues)
            else:
                # Sequential execution
                for rule in batch:
                    rule_config = dict(rule.config)
                    if rule.meta.id in config_overrides:
                        rule_config.update(config_overrides[rule.meta.id])
                    result = self._run_single_rule(rule, document, profile, rule_config)
                    self._update_stats(result)
                    issues.extend(result.issues)

            if progress_callback:
                pct = (batch_idx + 1) / total_batches * 100
                progress_callback(f"batch{batch_idx}", pct)

        return issues

    def _run_single_rule(
        self,
        rule: RegisteredRule,
        document: DocumentModel,
        profile: Profile,
        rule_config: dict[str, Any],
    ) -> RuleResult:
        """Execute a single rule with timeout, error handling, and runtime overrides."""
        start = time.time()

        # Apply runtime overrides
        overrides = self._rule_overrides.get(rule.meta.id, {})
        if overrides.get("enabled_by_default") is False:
            return RuleResult(
                rule_id=rule.meta.id,
                issues=[],
                execution_time_ms=0,
                success=True,
                version=rule.meta.version,
            )
        severity_override = overrides.get("severity")
        priority_override = overrides.get("priority")
        confidence_override = overrides.get("confidence")

        # Check cache
        cache_key = f"{rule.meta.id}:{hash(document.text[:100])}"
        if cache_key in self._cache:
            cached_time, cached_issues = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return RuleResult(
                    rule_id=rule.meta.id,
                    issues=cached_issues,
                    execution_time_ms=0,
                    success=True,
                    version=rule.meta.version,
                )

        try:
            # Timeout enforcement (runs in thread if timeout configured)
            timeout = overrides.get("timeout_ms", rule.meta.timeout_ms)
            if timeout > 0 and timeout < 30000:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(rule.fn, document, profile, rule_config)
                    result_issues = future.result(timeout=timeout / 1000)
            else:
                result_issues = rule.fn(document, profile, rule_config)

            elapsed = (time.time() - start) * 1000

            # Update cache
            self._cache[cache_key] = (time.time(), result_issues)

            # Apply severity/confidence overrides to issues
            if severity_override or confidence_override:
                modified_issues = []
                for iss in result_issues:
                    if severity_override:
                        iss = Issue(
                            id=iss.id, category=iss.category, rule_id=iss.rule_id,
                            severity=severity_override, message=iss.message,
                            recommendation=iss.recommendation, evidence=iss.evidence,
                            confidence=confidence_override or iss.confidence,
                            source=iss.source, autofix_allowed=iss.autofix_allowed,
                        )
                    modified_issues.append(iss)
                result_issues = modified_issues

            return RuleResult(
                rule_id=rule.meta.id,
                issues=result_issues,
                execution_time_ms=elapsed,
                success=True,
                version=rule.meta.version,
            )

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            logger.warning(f"Rule '{rule.meta.id}' failed after {elapsed:.0f}ms: {e}")

            error_issue = Issue(
                id=f"rule-error-{rule.meta.id}",
                category="internal",
                rule_id=rule.meta.id,
                severity=Severity.LOW,
                message=f"Rule '{rule.meta.name}' failed: {e}",
                recommendation="Check rule implementation or document compatibility.",
                evidence=Evidence("Rule execution error", 0, 0, "internal"),
                confidence=0,
                source="system",
            )
            return RuleResult(
                rule_id=rule.meta.id,
                issues=[error_issue],
                execution_time_ms=elapsed,
                success=False,
                error=str(e)[:500],
                version=rule.meta.version,
            )

    def _update_stats(self, result: RuleResult) -> None:
        """Update execution statistics for a rule."""
        stats = self._stats.get(result.rule_id)
        if not stats:
            return
        stats.total_runs += 1
        stats.total_issues += len(result.issues)
        stats.total_time_ms += result.execution_time_ms
        stats.avg_time_ms = stats.total_time_ms / stats.total_runs
        stats.last_run = time.time()
        if not result.success:
            stats.error_count += 1

    # ── Statistics ────────────────────────────────────────────────────────

    def get_statistics(self) -> dict[str, Any]:
        """Get comprehensive rule execution statistics."""
        return {
            "total_rules": len(self._rules),
            "total_packs": len({r.meta.pack_id for r in self._rules.values() if r.meta.pack_id}),
            "categories": self.count_by_category(),
            "rule_stats": {
                rid: {
                    "total_runs": s.total_runs,
                    "total_issues": s.total_issues,
                    "avg_time_ms": round(s.avg_time_ms, 2),
                    "error_count": s.error_count,
                    "last_run": s.last_run,
                }
                for rid, s in self._stats.items() if s.total_runs > 0
            },
            "cache_size": len(self._cache),
            "parallel_enabled": self.enable_parallel,
        }

    def get_execution_summary(self) -> dict[str, Any]:
        """Get summary of rule execution performance."""
        total_time = sum(s.total_time_ms for s in self._stats.values())
        total_issues = sum(s.total_issues for s in self._stats.values())
        total_errors = sum(s.error_count for s in self._stats.values())
        return {
            "total_executions": sum(s.total_runs for s in self._stats.values()),
            "total_time_ms": round(total_time, 2),
            "total_issues_found": total_issues,
            "total_errors": total_errors,
            "avg_time_per_rule_ms": round(total_time / max(len(self._stats), 1), 2),
        }

    # ── Configuration Overrides Runtime ───────────────────────────────────
    # Uses mutable override dicts instead of mutating frozen dataclasses

    def configure_rule(self, rule_id: str, **overrides: Any) -> None:
        """Dynamically configure a rule at runtime (uses mutable overrides)."""
        rule = self._rules.get(rule_id)
        if not rule:
            raise ValueError(f"Rule '{rule_id}' not found")
        for key, value in overrides.items():
            if hasattr(rule.meta, key):
                # Store in mutable override dict instead of mutating frozen dataclass
                self._rule_overrides[rule_id] = self._rule_overrides.get(rule_id, {})
                self._rule_overrides[rule_id][key] = value
            else:
                rule.config[key] = value

    def configure_category(
        self,
        category: str,
        enabled: bool | None = None,
        severity_override: Severity | None = None,
    ) -> int:
        """Configure all rules in a category. Returns count of affected rules."""
        count = 0
        for r_id, rule in self._rules.items():
            if rule.meta.category == category:
                if enabled is not None:
                    self._rule_overrides.setdefault(r_id, {})["enabled_by_default"] = enabled
                if severity_override is not None:
                    self._rule_overrides.setdefault(r_id, {})["severity"] = severity_override
                count += 1
        return count

    def get_effective_config(self, rule_id: str) -> dict[str, Any]:
        """Get the effective configuration for a rule (base + overrides)."""
        rule = self._rules.get(rule_id)
        if not rule:
            return {}
        overrides = self._rule_overrides.get(rule_id, {})
        return {
            "enabled": overrides.get("enabled_by_default", rule.meta.enabled_by_default),
            "severity": overrides.get("severity", rule.meta.severity),
            "config": rule.config,
        }


# ─── Global registry instance ─────────────────────────────────────────────────

registry = RuleRegistry()


# ─── Decorator for convenient registration ────────────────────────────────────

def rule(
    id: str,
    category: str,
    name: str,
    description: str = "",
    severity: Severity = Severity.MEDIUM,
    priority: int = 0,
    confidence: int = 90,
    source: str = "syntax-rule",
    autofix_allowed: bool = False,
    pack_id: str = "",
    pack_version: str = "",
    version: str = "1.0.0",
    tags: list[str] | None = None,
    **kwargs,
):
    """Decorator to register a rule function with the global registry."""
    def decorator(fn: RuleFn) -> RuleFn:
        meta = RuleMeta(
            id=id, category=category, name=name, description=description,
            severity=severity, priority=priority, confidence=confidence,
            source=source, autofix_allowed=autofix_allowed, pack_id=pack_id,
            pack_version=pack_version, version=version,
            tags=tags or [],
        )
        registry.register(id, meta, fn, kwargs.get("config"))
        return fn
    return decorator
