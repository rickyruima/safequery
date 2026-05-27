# Promotional posts — safequery

Repo: https://github.com/rickyruima/safequery
Generated: 2026-05-27T05:02:41.604189+00:00

## twitter (280 chars)

Your AI agent will eventually emit a DELETE with no WHERE.

SafeQuery parses SQL into an AST (pglast, not regex) and blocks catastrophic queries before they hit your DB. Local, P99 <5ms, 17 rules, two-line API.

Apache 2.0:
https://github.com/rickyruima/safequery

#PostgreSQL #AI

## linkedin (1807 chars)

Ever watched an AI agent generate a `DELETE` with no `WHERE` clause and send it straight to production?

That's the failure mode that keeps me up at night. We're handing LLMs direct SQL access, and the model doesn't know the difference between a routine cleanup and dropping a table. One bad token and you're restoring from backup.

I built SafeQuery to sit between the agent and the database as a check that doesn't rely on the model behaving.

Here's the core idea: it parses the agent's SQL into an actual AST using pglast — the real Postgres parser — not regex or string matching. Regex catches the `DROP TABLE` you thought of and misses the three you didn't. An AST sees the query the way the database will.

What it does:

- 17 configurable safety rules across BLOCK / WARN / LOG levels (unbounded DELETE/UPDATE, schema changes, etc.)
- Runs fully local. Zero API calls, P99 under 5ms — it won't slow your agent loop down.
- Two-line Python API to drop into your tool-calling code, plus a CLI so you can gate SQL in CI.
- Dry-run mode so you can tune rules against real traffic before anything starts blocking.

The reason it's deterministic matters. A safety layer that's itself an LLM call adds latency, cost, and a second model that can be wrong. Parsing is just parsing — same input, same answer, every time.

Who this is for: anyone shipping agents with database access — text-to-SQL tools, analytics copilots, autonomous data pipelines. If your agent can write SQL, it can write SQL you didn't intend.

Apache 2.0, Python 3.10+. Code and docs here:
https://github.com/rickyruima/safequery

If you're running agents against a real database, I'd genuinely like to hear how you're handling this today — and what rules you'd want added.

#AIAgents #DatabaseSecurity #LLM #DataEngineering #OpenSource

## reddit (3908 chars)
**Title:** safequery: A safety layer between your AI agent and your database — local SQL risk analysis

**TL;DR:** I built SafeQuery, a local Python library that parses your AI agent's SQL into an AST (using pglast, the real Postgres parser) and blocks dangerous queries — unqualified DELETEs, `DROP TABLE`, etc. — before they hit your DB. No API calls, P99 under 5ms, 17 configurable rules, Apache 2.0. Repo: https://github.com/rickyruima/safequery

---

I've been building agents that talk to a SQL database directly, and the thing that kept me up at night wasn't the agent being *wrong* — it was the agent being confidently destructive. An LLM that generates `DELETE FROM users` without a WHERE clause, or decides a `DROP TABLE` is a reasonable way to "clean up," will happily do that if you've given it a connection. Prompt-level guardrails ("never delete data!") are not a real safety boundary. They're a suggestion.

The usual reaction is to write a regex that looks for scary keywords. I went down that road and hated it. Regex on SQL is a losing game — comments, string literals containing the word "drop", weird whitespace, CTEs, subqueries. You either block legitimate queries or miss the bad ones, and you can never be sure which.

So I made **SafeQuery**. The core idea: don't pattern-match the SQL text, *parse* it. It runs the query through `pglast` (libpg_query — the actual PostgreSQL parser) to get a real AST, then walks the tree and applies rules against the structure. A `DELETE` with no WHERE clause is a fact about the parse tree, not a string it happened to find.

What it actually does:

- **Real AST parsing**, not string matching. If Postgres can parse it, SafeQuery understands its structure.
- **Runs locally, zero network calls.** It's a parser, not a service. P99 latency is under 5ms on my machine, so you can put it in the hot path of every agent query without thinking about it.
- **17 built-in rules** across three levels — `BLOCK` (refuse the query), `WARN` (allow but flag), `LOG` (just record). Things like unqualified DELETE/UPDATE, DROP/TRUNCATE, schema changes, etc. You configure which rules fire and at what level.
- **Dry-run mode** so you can point it at your real query traffic and see what *would* have been blocked before you actually start blocking. This mattered a lot to me — turning on a safety layer that silently breaks your app is its own kind of outage.
- **Two-line Python API**, plus a CLI so you can run it in CI against a file of queries.

Rough shape of the Python usage:

```python
from safequery import SafeQuery

sq = SafeQuery()
result = sq.check("DELETE FROM users")  # no WHERE → blocked

if not result.allowed:
    raise PermissionError(result.reason)
```

You drop that between your agent's generated SQL and your `execute()` call. That's the whole integration.

Some honest limitations, since I'd want to know these before adding a dependency:

- It targets **PostgreSQL syntax** (that's what pglast parses). MySQL/SQLite users — the AST won't map cleanly, so this isn't for you right now.
- It's a **static analysis** layer. It reasons about query structure, not runtime state. It can tell that an UPDATE has no WHERE clause; it can't tell you that an UPDATE *with* a WHERE clause matches 4 million rows.
- It's **not auth or row-level security.** It's a blast-radius limiter for the "the agent did something structurally catastrophic" failure mode. You still need real DB permissions underneath it.
- Requires **Python 3.10+**.

Disclosure: I wrote it, so I'm obviously biased. It's Apache 2.0, no telemetry, nothing to sign up for. I'm mostly posting because I suspect a bunch of people here are wiring LLMs up to databases right now and reaching for the same regex I started with.

If you try it, I'd genuinely like to hear where the rules are too aggressive or too loose — the default rule set is my opinion, and I'd rather it reflect more than one person's paranoia. Issues and PRs welcome.

Repo: https://github.com/rickyruima/safequery

## hackernews (2349 chars)
**Title:** Show HN: safequery – A safety layer between your AI agent and your database — local SQL risk analysis

Show HN: SafeQuery – a local SQL safety layer that blocks dangerous queries from AI agents

I've been building agents that generate SQL and run it against a real Postgres database. The problem is obvious in hindsight: an LLM that's mostly right will eventually produce a `DELETE` without a `WHERE`, a `DROP TABLE`, or an `UPDATE` that touches every row. Hoping the model behaves isn't a safety strategy, and wrapping everything in read-only transactions or per-query human approval got in the way of the agent actually doing work.

SafeQuery sits between the agent and the database. It parses the SQL into an AST and checks it against a set of rules before the query executes.

What it does:

- Parses SQL using pglast (libpg_query, the actual Postgres parser) rather than regex or string matching. Regex-based checks are easy to fool — comments, whitespace, quoted identifiers, subqueries — and false confidence is worse than no check. Working on the parse tree means a rule like "UPDATE/DELETE without a WHERE clause" looks at the WHERE node, not a substring.
- 17 built-in rules across three levels: BLOCK (reject), WARN (allow but flag), LOG (record). Things like missing WHERE on UPDATE/DELETE, DROP/TRUNCATE, DDL, and a few others. Levels are configurable, so you can start permissive and tighten.
- Runs locally, no API calls. P99 is under 5ms on my machine since it's just a parse and tree walk. It's in the hot path of every query, so it can't be slow or depend on a network.
- Dry-run mode so you can point it at real query logs and see what would have been blocked before you actually turn on enforcement.

Usage is two lines in Python (parse + check, raises on a BLOCK), and there's a CLI so you can run the same checks in CI against migrations or a query corpus.

Some deliberate limitations: it's Postgres dialect only right now (pglast is Postgres-specific), Python 3.10+, Apache 2.0. It is not a substitute for database permissions — least-privilege roles are still the real boundary. This is a deterministic layer in front of that, aimed at catching the catastrophic-but-syntactically-valid query the model didn't mean to send.

Repo: https://github.com/rickyruima/safequery

Interested in what rules people would want that aren't in the default set, and whether the AST approach holds up against SQL other people's agents generate.
