"""Tests for the CLI."""

from click.testing import CliRunner

from safequery.cli import main


class TestCLI:
    def setup_method(self):
        self.runner = CliRunner()

    def test_check_block(self):
        result = self.runner.invoke(main, ["check", "DROP TABLE users"])
        assert result.exit_code == 1
        assert "BLOCK" in result.output

    def test_check_allow(self):
        result = self.runner.invoke(main, ["check", "SELECT id FROM orders WHERE id = 1"])
        assert result.exit_code == 0
        assert "ALLOW" in result.output

    def test_check_warn(self):
        result = self.runner.invoke(main, ["check", "SELECT * FROM users"])
        assert result.exit_code == 0
        assert "LOG" in result.output

    def test_check_with_dry_run(self):
        result = self.runner.invoke(main, ["check", "--dry-run", "DROP TABLE users"])
        assert result.exit_code == 0  # not blocked in dry-run
        assert "WARN" in result.output

    def test_version(self):
        result = self.runner.invoke(main, ["--version"])
        assert "0.1.0" in result.output
