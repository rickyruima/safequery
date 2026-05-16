"""Core SafeQuery checker."""

from pathlib import Path
from typing import Optional

from safequery.config import SafeQueryConfig
from safequery.models import CheckResult
from safequery.parser import parse_sql
from safequery.rules import RulesEngine


class SafeQuery:
    """Main SafeQuery interface for checking SQL safety."""

    def __init__(self, config: Optional[SafeQueryConfig] = None):
        self.config = config or SafeQueryConfig.default()
        self.engine = RulesEngine()

    @classmethod
    def from_file(cls, path: str | Path) -> "SafeQuery":
        """Create SafeQuery instance from a YAML config file."""
        config = SafeQueryConfig.from_yaml(path)
        return cls(config=config)

    @classmethod
    def from_dict(cls, data: dict) -> "SafeQuery":
        """Create SafeQuery instance from a config dictionary."""
        config = SafeQueryConfig.from_dict(data)
        return cls(config=config)

    def check(self, sql: str) -> CheckResult:
        """Check a SQL query for safety violations.

        Returns a CheckResult with the recommended action and any violations.
        """
        parsed = parse_sql(sql, dialect=self.config.dialect)

        if parsed.error:
            # If we can't parse it, we can't verify it's safe
            return CheckResult(action="BLOCK", sql=sql)

        violations = self.engine.evaluate(parsed, self.config)

        if not violations:
            return CheckResult(action="ALLOW", sql=sql)

        # Determine overall action based on highest severity violation
        action_priority = {"BLOCK": 0, "WARN": 1, "LOG": 2, "ALLOW": 3}
        overall_action = min(
            (v.action for v in violations),
            key=lambda a: action_priority.get(a, 99),
        )

        # In dry-run mode, downgrade BLOCK to WARN
        if self.config.dry_run_mode and overall_action == "BLOCK":
            overall_action = "WARN"

        return CheckResult(action=overall_action, sql=sql, violations=violations)
