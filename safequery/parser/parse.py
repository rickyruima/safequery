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
    is_alter_drop_column: bool = False
    has_tautology_where: bool = False  # WHERE 1=1 or WHERE true
    in_clause_max_values: int = 0
    has_cross_join: bool = False
    is_grant_all: bool = False
    join_count: int = 0
    has_union: bool = False
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
    is_alter_drop_column = _is_alter_drop_column(ast)
    has_tautology_where = _has_tautology_where(ast)
    in_clause_max_values = _get_in_clause_max_values(ast)
    has_cross_join = _has_cross_join(ast, sql)
    is_grant_all = _is_grant_all(sql)
    join_count = _get_join_count(ast)
    has_union = _has_union(ast, sql)

    return ParsedQuery(
        raw_sql=sql,
        statement_type=stmt_type,
        tables=tables,
        has_where=has_where,
        has_limit=has_limit,
        subquery_depth=subquery_depth,
        is_select_star=is_select_star,
        is_alter_drop_column=is_alter_drop_column,
        has_tautology_where=has_tautology_where,
        in_clause_max_values=in_clause_max_values,
        has_cross_join=has_cross_join,
        is_grant_all=is_grant_all,
        join_count=join_count,
        has_union=has_union,
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


def _is_alter_drop_column(ast: exp.Expression) -> bool:
    """Check if this is an ALTER TABLE ... DROP COLUMN statement."""
    if not isinstance(ast, exp.Alter):
        return False
    sql_upper = ast.sql().upper()
    return "DROP" in sql_upper and "COLUMN" in sql_upper


def _has_tautology_where(ast: exp.Expression) -> bool:
    """Check if WHERE clause is a tautology like WHERE 1=1 or WHERE true."""
    where = ast.find(exp.Where)
    if where is None:
        return False
    condition = where.this
    if isinstance(condition, exp.EQ):
        left = condition.left
        right = condition.right
        if isinstance(left, exp.Literal) and isinstance(right, exp.Literal):
            if left.this == right.this:
                return True
    if isinstance(condition, exp.Boolean) and condition.this:
        return True
    return False


def _get_in_clause_max_values(ast: exp.Expression) -> int:
    """Get the maximum number of values in any IN clause."""
    max_values = 0
    for in_node in ast.find_all(exp.In):
        # Count the values in the IN expression
        expressions = in_node.expressions
        if expressions:
            max_values = max(max_values, len(expressions))
    return max_values


def _has_cross_join(ast: exp.Expression, sql: str) -> bool:
    """Check for CROSS JOIN or implicit cross join (FROM a, b)."""
    # Check for explicit CROSS JOIN
    for join in ast.find_all(exp.Join):
        if hasattr(join, 'kind') and join.kind and join.kind.upper() == "CROSS":
            return True
        # Also check the join side
        join_sql = join.sql().upper()
        if "CROSS JOIN" in join_sql:
            return True

    # Check for implicit cross join (FROM a, b) - multiple tables in FROM without JOIN
    sql_upper = sql.upper().strip()
    if isinstance(ast, exp.Select):
        from_clause = ast.find(exp.From)
        if from_clause:
            # If there are multiple tables in FROM and no JOIN keywords connecting them
            # that indicates an implicit cross join
            tables_in_from = list(from_clause.find_all(exp.Table))
            # Also check for comma-separated tables (implicit cross join)
            # sqlglot represents "FROM a, b" with Join nodes of kind ""
            joins = list(ast.find_all(exp.Join))
            for join in joins:
                if not join.kind or join.kind == "":
                    # This is an implicit cross join (comma-separated)
                    return True

    # Fallback: check raw SQL for CROSS JOIN
    if "CROSS JOIN" in sql_upper:
        return True

    return False


def _is_grant_all(sql: str) -> bool:
    """Check for GRANT ALL PRIVILEGES."""
    sql_upper = sql.upper().strip()
    return sql_upper.startswith("GRANT") and ("ALL PRIVILEGES" in sql_upper or "ALL" in sql_upper.split("GRANT")[1].split("ON")[0] if "ON" in sql_upper else "ALL" in sql_upper)


def _get_join_count(ast: exp.Expression) -> int:
    """Count the number of JOIN operations."""
    return len(list(ast.find_all(exp.Join)))


def _has_union(ast: exp.Expression, sql: str) -> bool:
    """Check if query uses UNION."""
    if ast.find(exp.Union):
        return True
    # Fallback check on raw SQL
    sql_upper = sql.upper()
    return " UNION " in sql_upper
