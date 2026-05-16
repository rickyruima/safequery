"""Data models for SafeQuery."""

from dataclasses import dataclass, field


@dataclass
class Violation:
    """A single rule violation found in a SQL query."""

    rule: str
    reason: str
    severity: str  # "critical", "high", "medium", "low"
    action: str  # "BLOCK", "WARN", "LOG"


@dataclass
class CheckResult:
    """Result of checking a SQL query."""

    action: str  # "BLOCK", "WARN", "LOG", "ALLOW"
    sql: str
    violations: list[Violation] = field(default_factory=list)

    @property
    def reason(self) -> str:
        """Human-readable summary of all violations."""
        if not self.violations:
            return "Query is safe."
        return "; ".join(v.reason for v in self.violations)

    @property
    def rule(self) -> str:
        """Primary rule that triggered the action."""
        if not self.violations:
            return ""
        return self.violations[0].rule

    @property
    def severity(self) -> str:
        """Highest severity among violations."""
        if not self.violations:
            return "low"
        priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return min(self.violations, key=lambda v: priority.get(v.severity, 99)).severity

    @property
    def is_blocked(self) -> bool:
        return self.action == "BLOCK"

    @property
    def is_allowed(self) -> bool:
        return self.action == "ALLOW"
