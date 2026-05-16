"""Tests for the core SafeQuery API."""

from safequery import SafeQuery, CheckResult
from safequery.config import SafeQueryConfig


class TestSafeQueryCheck:
    def setup_method(self):
        self.sq = SafeQuery()

    def test_block_drop_table(self):
        result = self.sq.check("DROP TABLE users")
        assert result.action == "BLOCK"
        assert result.is_blocked
        assert "DROP" in result.reason

    def test_block_delete_without_where(self):
        result = self.sq.check("DELETE FROM users")
        assert result.action == "BLOCK"

    def test_block_update_without_where(self):
        result = self.sq.check("UPDATE users SET x = 1")
        assert result.action == "BLOCK"

    def test_block_truncate(self):
        result = self.sq.check("TRUNCATE TABLE users")
        assert result.action == "BLOCK"

    def test_warn_delete_without_limit(self):
        # Delete from a non-protected table with WHERE but no LIMIT
        config = SafeQueryConfig(protected_tables=[])
        sq = SafeQuery(config=config)
        result = sq.check("DELETE FROM logs WHERE created_at < '2020-01-01'")
        assert result.action == "WARN"

    def test_allow_safe_select(self):
        result = self.sq.check("SELECT id, name FROM orders WHERE id = 1")
        assert result.action == "ALLOW"
        assert result.is_allowed

    def test_allow_insert(self):
        result = self.sq.check("INSERT INTO logs (msg) VALUES ('test')")
        assert result.action == "ALLOW"


class TestDryRunMode:
    def test_dry_run_downgrades_block(self):
        config = SafeQueryConfig(dry_run_mode=True)
        sq = SafeQuery(config=config)
        result = sq.check("DROP TABLE users")
        assert result.action == "WARN"  # downgraded from BLOCK


class TestFromDict:
    def test_from_dict(self):
        sq = SafeQuery.from_dict({
            "dialect": "postgres",
            "protected_tables": ["accounts"],
            "dry_run_mode": False,
        })
        result = sq.check("DROP TABLE accounts")
        assert result.action == "BLOCK"


class TestCheckResultProperties:
    def test_reason(self):
        sq = SafeQuery()
        result = sq.check("DROP TABLE users")
        assert len(result.reason) > 0

    def test_severity(self):
        sq = SafeQuery()
        result = sq.check("DROP TABLE users")
        assert result.severity == "critical"

    def test_rule(self):
        sq = SafeQuery()
        result = sq.check("DROP TABLE users")
        assert result.rule == "drop_table"
