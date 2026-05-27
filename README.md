# SafeQuery

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](https://opensource.org/licenses/Apache-2.0)

**A safety layer between your AI agent and your database. Stop catastrophic SQL before it executes.**

---

## The Problem

Replit Agent deleted a production database. An AI coding assistant ran `DELETE FROM users` without a WHERE clause. These aren't hypothetical — they happened.

Every AI agent with database access is one hallucination away from a catastrophe. LLMs don't understand "this is production." They don't know which tables are critical. They routinely generate SQL that is syntactically valid but semantically destructive.

There is no deterministic last line of defense. Until now.

---

## What It Does

SafeQuery parses SQL into an AST and checks it against 17 safety rules — **before** the query hits your database.

```python
from safequery import SafeQuery

sq = SafeQuery()
result = sq.check("DELETE FROM users")
# result.action == "BLOCK"
# result.reason == "DELETE without WHERE clause on table(s): users"
```

No API calls. No network latency. No LLM-checking-LLM nonsense. Pure deterministic verification in well under a millisecond.

---

## Why This Exists

LLMs + databases = danger:

- LLMs don't know which environment they're running in
- LLMs don't know which tables are critical (`users`, `payments`, `audit_log`)
- LLMs generate "syntactically correct, semantically catastrophic" SQL regularly
- Prompt engineering is not a safety mechanism

Existing mitigations fail:
- **Human review** — impossible when agents auto-execute
- **DB permissions** — too coarse (can't distinguish safe DELETE from unsafe DELETE)
- **String matching** (LangChain's approach) — trivially bypassed
- **LLM-based review** — using an LLM to check an LLM is circular

SafeQuery is a **deterministic verifier**. AST parsing + rule engine. No probabilistic guessing.

---

## Features

- **17 safety rules** across BLOCK / WARN / LOG severity levels
- **SQL AST parsing** via [sqlglot](https://github.com/tobymao/sqlglot) — not regex, not string matching; works across dialects (Postgres, MySQL, SQLite, …), Postgres by default
- **Zero latency** — runs locally, no API calls (measured P99 ≈ 0.2ms, see `benchmarks/`)
- **YAML configuration** — customize rules, actions, and protected tables
- **Protected tables** — mark critical tables for extra scrutiny
- **CLI tool** — check queries from the terminal, integrate into CI
- **Python API** — two lines to integrate into any agent framework
- **Dry-run mode** — audit without blocking while you tune rules

---

## Rules

| Rule | Default Action | What It Catches |
|------|---------------|-----------------|
| `delete_without_where` | BLOCK | `DELETE FROM users` (no WHERE) |
| `update_without_where` | BLOCK | `UPDATE accounts SET balance=0` (no WHERE) |
| `drop_table` | BLOCK | `DROP TABLE users` |
| `truncate` | BLOCK | `TRUNCATE payments` |
| `alter_table_drop_column` | BLOCK | `ALTER TABLE users DROP COLUMN email` |
| `delete_all_rows` | BLOCK | `DELETE FROM users WHERE 1=1` (tautological WHERE) |
| `update_all_rows` | WARN | `UPDATE users SET active=false WHERE 1=1` |
| `delete_without_limit` | WARN | `DELETE FROM logs WHERE created < '2020-01-01'` (no LIMIT) |
| `update_without_limit` | WARN | `UPDATE users SET verified=true WHERE signup < '2024-01-01'` |
| `protected_table_modification` | WARN | Any DML on tables you've marked as protected |
| `large_in_clause` | WARN | `SELECT * FROM users WHERE id IN (1, 2, ..., 500)` (>100 values) |
| `cross_join` | WARN | Cartesian products that explode row counts |
| `grant_all` | WARN | `GRANT ALL PRIVILEGES` |
| `select_star` | LOG | `SELECT * FROM large_table` |
| `deep_subquery` | LOG | Subqueries nested 3+ levels deep |
| `multiple_table_join` | LOG | Queries joining 4+ tables |
| `union_without_limit` | LOG | UNION queries without an outer LIMIT |

Every rule's action is configurable. BLOCK becomes WARN becomes LOG — your call.

---

## Quick Start

```bash
pip install safequery
```

```python
from safequery import SafeQuery

sq = SafeQuery()

# Blocked — no WHERE clause
result = sq.check("DELETE FROM users")
assert result.action == "BLOCK"
assert result.is_blocked

# Warned — WHERE exists but no LIMIT
result = sq.check("DELETE FROM logs WHERE created_at < '2020-01-01'")
assert result.action == "WARN"

# Allowed — safe query
result = sq.check("SELECT id, name FROM users WHERE id = 42")
assert result.action == "ALLOW"
assert result.is_allowed
```

---

## CLI Usage

```bash
# Check a single query
$ safequery check "DROP TABLE users"
[BLOCK] DROP statement detected on table(s): users

  Rule: drop_table
  Severity: critical
  Action: BLOCK
  Reason: DROP statement detected on table(s): users

$ safequery check "SELECT id FROM users WHERE id = 1"
[ALLOW] Query is safe.

# Use a custom config
$ safequery check "DELETE FROM logs WHERE id = 5" --config safequery.yaml

# Dry-run mode (BLOCK becomes WARN)
$ safequery check "DROP TABLE users" --dry-run
[WARN] DROP statement detected on table(s): users
```

Exit code is `1` on BLOCK — use it in CI pipelines.

---

## Configuration

Create a `safequery.yaml`:

```yaml
dialect: postgres

protected_tables:
  - users
  - payments
  - audit_log
  - subscriptions

policy:
  catastrophic:
    delete_without_where: BLOCK
    update_without_where: BLOCK
    drop_table: BLOCK
    truncate: BLOCK
    alter_table_drop_column: BLOCK
    delete_all_rows: BLOCK

  dangerous:
    delete_without_limit: WARN
    update_without_limit: WARN
    protected_table_modification: WARN
    update_all_rows: WARN
    large_in_clause: WARN
    cross_join: WARN
    grant_all: WARN

  suspicious:
    select_star: LOG
    deep_subquery: LOG
    multiple_table_join: LOG
    union_without_limit: LOG

dry_run_mode: false
```

Load it:

```python
sq = SafeQuery.from_file("safequery.yaml")
```

---

## Use with AI Agents

### LangChain

```python
from langchain_openai import ChatOpenAI
from langchain.agents import create_sql_agent
from safequery import SafeQuery

sq = SafeQuery.from_file("safequery.yaml")

def safe_db_execute(sql: str):
    """Wrap your DB executor with SafeQuery."""
    result = sq.check(sql)
    if result.is_blocked:
        return f"BLOCKED: {result.reason}"
    return db.execute(sql)
```

### OpenAI Function Calling

```python
from openai import OpenAI
from safequery import SafeQuery

client = OpenAI()
sq = SafeQuery()

def handle_sql_tool_call(sql: str) -> str:
    """Safety check before executing AI-generated SQL."""
    check = sq.check(sql)

    if check.is_blocked:
        # Return error to the model so it can self-correct
        return f"Query blocked: {check.reason}. Please rewrite."

    if check.action == "WARN":
        # Log but allow
        print(f"WARNING: {check.reason}")

    return db.execute(sql)
```

### Generic Agent Loop

```python
from safequery import SafeQuery

sq = SafeQuery()

def agent_execute_sql(sql: str):
    """Drop-in safety wrapper for any agent framework."""
    result = sq.check(sql)

    match result.action:
        case "BLOCK":
            raise ValueError(f"Unsafe query blocked: {result.reason}")
        case "WARN":
            logger.warning(f"Risky query: {result.reason}")
            return db.execute(sql)
        case _:
            return db.execute(sql)
```

---

## API Reference

```python
from safequery import SafeQuery

# Default config
sq = SafeQuery()

# From YAML file
sq = SafeQuery.from_file("safequery.yaml")

# From dictionary
sq = SafeQuery.from_dict({"dialect": "postgres", "protected_tables": ["users"]})

# Check a query
result = sq.check("SELECT * FROM users")

result.action       # "BLOCK" | "WARN" | "LOG" | "ALLOW"
result.reason       # Human-readable explanation
result.violations   # List of Violation objects
result.is_blocked   # True if action == "BLOCK"
result.is_allowed   # True if action == "ALLOW"
result.severity     # "critical" | "high" | "medium" | "low"
result.rule         # Primary rule that triggered
```

---

## License

Apache 2.0
