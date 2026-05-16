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


def _check_alter_table_drop_column(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.is_alter_drop_column:
        return Violation(
            rule="alter_table_drop_column",
            reason=f"ALTER TABLE ... DROP COLUMN on table(s): {', '.join(query.tables) or 'unknown'}",
            severity="critical",
            action=config.policy.alter_table_drop_column,
        )
    return None


def _check_delete_all_rows(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.statement_type == "DELETE" and query.has_tautology_where:
        return Violation(
            rule="delete_all_rows",
            reason=f"DELETE with tautological WHERE (e.g., WHERE 1=1) on table(s): {', '.join(query.tables) or 'unknown'}",
            severity="critical",
            action=config.policy.delete_all_rows,
        )
    return None


def _check_update_all_rows(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.statement_type == "UPDATE" and query.has_tautology_where:
        return Violation(
            rule="update_all_rows",
            reason=f"UPDATE with tautological WHERE (e.g., WHERE 1=1) on table(s): {', '.join(query.tables) or 'unknown'}",
            severity="high",
            action=config.policy.update_all_rows,
        )
    return None


def _check_large_in_clause(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.in_clause_max_values > 100:
        return Violation(
            rule="large_in_clause",
            reason=f"IN clause with {query.in_clause_max_values} values (>100)",
            severity="medium",
            action=config.policy.large_in_clause,
        )
    return None


def _check_cross_join(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.has_cross_join:
        return Violation(
            rule="cross_join",
            reason=f"CROSS JOIN or implicit cross join detected on table(s): {', '.join(query.tables) or 'unknown'}",
            severity="medium",
            action=config.policy.cross_join,
        )
    return None


def _check_grant_all(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.is_grant_all:
        return Violation(
            rule="grant_all",
            reason="GRANT ALL PRIVILEGES detected",
            severity="high",
            action=config.policy.grant_all,
        )
    return None


def _check_multiple_table_join(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.join_count >= 3:  # 3 JOINs means 4+ tables
        return Violation(
            rule="multiple_table_join",
            reason=f"Query joins {query.join_count + 1} tables",
            severity="low",
            action=config.policy.multiple_table_join,
        )
    return None


def _check_union_without_limit(query: ParsedQuery, config: SafeQueryConfig) -> Optional[Violation]:
    if query.has_union and not query.has_limit:
        return Violation(
            rule="union_without_limit",
            reason="UNION query without outer LIMIT clause",
            severity="low",
            action=config.policy.union_without_limit,
        )
    return None


# Default rules in priority order
DEFAULT_RULES: list[Rule] = [
    Rule("delete_without_where", "Block DELETE without WHERE", _check_delete_without_where),
    Rule("update_without_where", "Block UPDATE without WHERE", _check_update_without_where),
    Rule("drop_table", "Block DROP TABLE", _check_drop_table),
    Rule("truncate", "Block TRUNCATE", _check_truncate),
    Rule("alter_table_drop_column", "Block ALTER TABLE DROP COLUMN", _check_alter_table_drop_column),
    Rule("delete_all_rows", "Block DELETE with WHERE 1=1", _check_delete_all_rows),
    Rule("update_all_rows", "Warn UPDATE with WHERE 1=1", _check_update_all_rows),
    Rule("delete_without_limit", "Warn DELETE without LIMIT", _check_delete_without_limit),
    Rule("update_without_limit", "Warn UPDATE without LIMIT", _check_update_without_limit),
    Rule("protected_table_modification", "Warn on protected table modification", _check_protected_tables),
    Rule("large_in_clause", "Warn large IN clause", _check_large_in_clause),
    Rule("cross_join", "Warn CROSS JOIN", _check_cross_join),
    Rule("grant_all", "Warn GRANT ALL PRIVILEGES", _check_grant_all),
    Rule("select_star", "Log SELECT *", _check_select_star),
    Rule("deep_subquery", "Log deep subqueries", _check_deep_subquery),
    Rule("multiple_table_join", "Log multiple table joins", _check_multiple_table_join),
    Rule("union_without_limit", "Log UNION without LIMIT", _check_union_without_limit),
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
