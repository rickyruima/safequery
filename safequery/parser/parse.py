"""SQL parsing using sqlglot."""

from dataclasses import dataclass, field
from typing import Optional

import sqlglot
from sqlglot import exp


@dataclass
class ParsedQuery:
    """Represents a parsed SQL query with extracted metadata."""

    raw_sql: str
    statement_type: str  # SELECT, DELETE, UPDATE, INSERT, DROP, TRUNCATE, CREATE, ALTER, etc.
    tables: list[str] = field(default_factory=list)
    has_where: bool = False
    has_limit: bool = False
    subquery_depth: int = 0
    is_select_star: bool = False
    error: Optional[str] = None


def parse_sql(sql: str, dialect: str = "postgres") -> ParsedQuery:
    """Parse a SQL string into a ParsedQuery object."""
    try:
        expressions = sqlglot.parse(sql, dialect=dialect)
    except sqlglot.errors.ParseError as e:
        return ParsedQuery(raw_sql=sql, statement_type="UNKNOWN", error=str(e))

    if not expressions or expressions[0] is None:
        return ParsedQuery(raw_sql=sql, statement_type="UNKNOWN", error="Empty or unparseable SQL")

    ast = expressions[0]
    stmt_type = _get_statement_type(ast)
    tables = _extract_tables(ast)
    has_where = _has_where_clause(ast)
    has_limit = _has_limit_clause(ast)
    subquery_depth = _get_subquery_depth(ast)
    is_select_star = _is_select_star(ast)

    return ParsedQuery(
        raw_sql=sql,
        statement_type=stmt_type,
        tables=tables,
        has_where=has_where,
        has_limit=has_limit,
        subquery_depth=subquery_depth,
        is_select_star=is_select_star,
    )


def _get_statement_type(ast: exp.Expression) -> str:
    """Determine the SQL statement type."""
    type_map = {
        exp.Select: "SELECT",
        exp.Delete: "DELETE",
        exp.Update: "UPDATE",
        exp.Insert: "INSERT",
        exp.Drop: "DROP",
        exp.Create: "CREATE",
        exp.Alter: "ALTER",
    }
    for cls, name in type_map.items():
        if isinstance(ast, cls):
            return name

    # Check for TRUNCATE
    sql_upper = ast.sql().upper()
    if "TRUNCATE" in sql_upper:
        return "TRUNCATE"

    return ast.__class__.__name__.upper()


def _extract_tables(ast: exp.Expression) -> list[str]:
    """Extract table names from the AST."""
    tables = []
    for table in ast.find_all(exp.Table):
        name = table.name
        if name:
            tables.append(name.lower())
    return list(dict.fromkeys(tables))  # dedupe preserving order


def _has_where_clause(ast: exp.Expression) -> bool:
    """Check if the statement has a WHERE clause."""
    # Check for WHERE with always-true conditions like WHERE 1=1
    where = ast.find(exp.Where)
    if where is None:
        return False
    # Check if it's a tautology like WHERE 1=1 or WHERE true
    condition = where.this
    if isinstance(condition, exp.EQ):
        left = condition.left
        right = condition.right
        if isinstance(left, exp.Literal) and isinstance(right, exp.Literal):
            if left.this == right.this:
                return False  # WHERE 1=1 is not a real WHERE
    if isinstance(condition, exp.Boolean) and condition.this:
        return False  # WHERE TRUE
    return True


def _has_limit_clause(ast: exp.Expression) -> bool:
    """Check if the statement has a LIMIT clause."""
    return ast.find(exp.Limit) is not None


def _get_subquery_depth(ast: exp.Expression, current_depth: int = 0) -> int:
    """Calculate maximum subquery nesting depth."""
    max_depth = current_depth
    for node in ast.walk():
        if isinstance(node, exp.Subquery):
            # Count ancestor Subquery nodes to determine depth
            depth = 0
            parent = node
            while parent is not None:
                if isinstance(parent, exp.Subquery):
                    depth += 1
                parent = parent.parent
            max_depth = max(max_depth, depth)
    return max_depth


def _is_select_star(ast: exp.Expression) -> bool:
    """Check if query uses SELECT *."""
    if not isinstance(ast, exp.Select):
        return False
    for select_expr in ast.find_all(exp.Star):
        return True
    return False
