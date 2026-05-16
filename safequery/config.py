"""Configuration loading for SafeQuery."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class PolicyConfig:
    """Policy configuration for rule actions."""

    delete_without_where: str = "BLOCK"
    update_without_where: str = "BLOCK"
    drop_table: str = "BLOCK"
    truncate: str = "BLOCK"
    delete_without_limit: str = "WARN"
    update_without_limit: str = "WARN"
    protected_table_modification: str = "WARN"
    select_star: str = "LOG"
    deep_subquery: str = "LOG"


@dataclass
class SafeQueryConfig:
    """Full SafeQuery configuration."""

    dialect: str = "postgres"
    protected_tables: list[str] = field(default_factory=lambda: ["users", "payments", "audit_log"])
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    dry_run_mode: bool = False

    @classmethod
    def from_yaml(cls, path: str | Path) -> "SafeQueryConfig":
        """Load configuration from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls._from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "SafeQueryConfig":
        """Load configuration from a dictionary."""
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> "SafeQueryConfig":
        policy_data = data.get("policy", {})
        # Flatten nested policy sections
        flat_policy = {}
        for section in ("catastrophic", "dangerous", "suspicious"):
            if section in policy_data:
                flat_policy.update(policy_data[section])
        if flat_policy:
            policy = PolicyConfig(**{k: v for k, v in flat_policy.items() if hasattr(PolicyConfig, k)})
        elif policy_data and not any(k in policy_data for k in ("catastrophic", "dangerous", "suspicious")):
            policy = PolicyConfig(**{k: v for k, v in policy_data.items() if hasattr(PolicyConfig, k)})
        else:
            policy = PolicyConfig()

        default_tables = ["users", "payments", "audit_log"]
        return cls(
            dialect=data.get("dialect", "postgres"),
            protected_tables=data.get("protected_tables", default_tables),
            policy=policy,
            dry_run_mode=data.get("dry_run_mode", False),
        )

    @classmethod
    def default(cls) -> "SafeQueryConfig":
        """Return default configuration."""
        return cls()
