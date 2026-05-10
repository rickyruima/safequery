# SafeQuery

> A safety layer between your AI agent and your database. Stop catastrophic SQL before it executes.

Python SDK that checks SQL queries before execution — blocks unbounded DELETEs, UPDATEs without WHERE, DROP TABLE, and more.

## Quick Start

```python
from safequery import SafeQuery

sq = SafeQuery(profile="production", dialect="postgresql")
result = sq.check("DELETE FROM users")
# result.action == "BLOCK"
```

## Tech Stack

- Python
- pglast (PostgreSQL AST parser)
- pydantic

## Status

Pre-development. See PRD: `../prd-2-ai-sql-safety-net.md`
