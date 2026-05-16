"""CLI interface for SafeQuery."""

import sys
from pathlib import Path

import click

from safequery.core import SafeQuery
from safequery.config import SafeQueryConfig


@click.group()
@click.version_option()
def main():
    """SafeQuery - Stop catastrophic SQL before it executes."""
    pass


@main.command()
@click.argument("sql")
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to safequery.yaml config file")
@click.option("--dialect", "-d", default="postgres", help="SQL dialect (default: postgres)")
@click.option("--dry-run", is_flag=True, help="Dry-run mode: BLOCK becomes WARN")
def check(sql: str, config: str | None, dialect: str, dry_run: bool):
    """Check a SQL query for safety violations.

    Example: safequery check "DROP TABLE users"
    """
    if config:
        sq = SafeQuery.from_file(config)
    else:
        cfg = SafeQueryConfig(dialect=dialect, dry_run_mode=dry_run)
        sq = SafeQuery(config=cfg)

    result = sq.check(sql)

    # Output
    action_colors = {"BLOCK": "red", "WARN": "yellow", "LOG": "blue", "ALLOW": "green"}
    color = action_colors.get(result.action, "white")

    click.echo(click.style(f"[{result.action}]", fg=color, bold=True) + f" {result.reason}")

    if result.violations:
        click.echo("")
        for v in result.violations:
            click.echo(f"  Rule: {v.rule}")
            click.echo(f"  Severity: {v.severity}")
            click.echo(f"  Action: {v.action}")
            click.echo(f"  Reason: {v.reason}")
            click.echo("")

    # Exit with non-zero code if blocked
    if result.action == "BLOCK":
        sys.exit(1)


if __name__ == "__main__":
    main()
