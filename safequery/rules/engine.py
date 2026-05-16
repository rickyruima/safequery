"""Rules engine that checks parsed SQL against safety rules."""

from dataclasses import dataclass
from typing import Callable, Optional

from safequery.config import SafeQueryConfig, PolicyConfig
from safequery.models import Violation
from safequery.parser.parse import ParsedQuery


@dataclass
class Rule:
    """A single safety rule."""

    name: str
    description: str
    check: Callable[[ParsedQuery, SafeQueryConfig], Optional[Violation]]


def _check_delete_without_where(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.statement_type == "DELETE" and not query.has_where:
        return Violation(
            rule="delete_without_where",
            reason=f"DELETE without WHERE clause on table(s): {', '.join(query.tables) or 'unknown'}",
            severity="critical",
            action=config.policy.delete_without_where,
        )
    return None


def _check_update_without_where(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.statement_type == "UPDATE" and not query.has_where:
        return Violation(
            rule="update_without_where",
            reason=f"UPDATE without WHERE clause on table(s): {', '.join(query.tables) or 'unknown'}",
            severity="critical",
            action=config.policy.update_without_where,
        )
    return None


def _check_drop_table(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.statement_type == "DROP":
        return Violation(
            rule="drop_table",
            reason=f"DROP statement detected on table(s): {', '.join(query.tables) or 'unknown'}",
            severity="critical",
            action=config.policy.drop_table,
        )
    return None


def _check_truncate(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.statement_type == "TRUNCATE":
        return Violation(
            rule="truncate",
            reason=f"TRUNCATE statement detected on table(s): {', '.join(query.tables) or 'unknown'}",
            severity="critical",
            action=config.policy.truncate,
        )
    return None


def _check_delete_without_limit(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.statement_type == "DELETE" and query.has_where and not query.has_limit:
        return Violation(
            rule="delete_without_limit",
            reason=f"DELETE without LIMIT clause on table(s): {', '.join(query.tables) or 'unknown'}",
            severity="high",
            action=config.policy.delete_without_limit,
        )
    return None


def _check_update_without_limit(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.statement_type == "UPDATE" and query.has_where and not query.has_limit:
        return Violation(
            rule="update_without_limit",
            reason=f"UPDATE without LIMIT clause on table(s): {', '.join(query.tables) or 'unknown'}",
            severity="high",
            action=config.policy.update_without_limit,
        )
    return None


def _check_protected_tables(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.statement_type in ("DELETE", "UPDATE", "DROP", "TRUNCATE", "ALTER"):
        protected = set(t.lower() for t in config.protected_tables)
        affected = [t for t in query.tables if t.lower() in protected]
        if affected:
            return Violation(
                rule="protected_table_modification",
                reason=f"Modification of protected table(s): {', '.join(affected)}",
                severity="high",
                action=config.policy.protected_table_modification,
            )
    return None


def _check_select_star(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.is_select_star:
        return Violation(
            rule="select_star",
            reason=f"SELECT * detected on table(s): {', '.join(query.tables) or 'unknown'}",
            severity="low",
            action=config.policy.select_star,
        )
    return None


def _check_deep_subquery(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.subquery_depth >= 3:
        return Violation(
            rule="deep_subquery",
            reason=f"Deeply nested subquery (depth: {query.subquery_depth})",
            severity="medium",
            action=config.policy.deep_subquery,
        )
    return None


# Default rules in priority order
DEFAULT_RULES: list[Rule] = [
    Rule("delete_without_where", "Block DELETE without WHERE", _check_delete_without_where),
    Rule("update_without_where", "Block UPDATE without WHERE", _check_update_without_where),
    Rule("drop_table", "Block DROP TABLE", _check_drop_table),
    Rule("truncate", "Block TRUNCATE", _check_truncate),
    Rule("delete_without_limit", "Warn DELETE without LIMIT", _check_delete_without_limit),
    Rule("update_without_limit", "Warn UPDATE without LIMIT", _check_update_without_limit),
    Rule("protected_table_modification", "Warn on protected table modification", _check_protected_tables),
    Rule("select_star", "Log SELECT *", _check_select_star),
    Rule("deep_subquery", "Log deep subqueries", _check_deep_subquery),
]


class RulesEngine:
    """Runs all rules against a parsed query."""

    def __init__(self, rules: Optional[list[Rule]] = None):
        self.rules = rules if rules is not None else DEFAULT_RULES

    def evaluate(self, query: ParsedQuery, config: SafeQueryConfig) -> list[Violation]:
        """Evaluate all rules and return violations."""
        violations = []
        for rule in self.rules:
            violation = rule.check(query, config)
            if violation is not None:
                violations.append(violation)
        return violations
