"""Tests for configuration loading."""

import tempfile
from pathlib import Path

from safequery.config import SafeQueryConfig


class TestDefaultConfig:
    def test_default_values(self):
        config = SafeQueryConfig.default()
        assert config.dialect == "postgres"
        assert "users" in config.protected_tables
        assert config.policy.delete_without_where == "BLOCK"
        assert config.dry_run_mode is False


class TestYamlConfig:
    def test_load_yaml(self):
        yaml_content = """
dialect: mysql
protected_tables:
  - accounts
  - transactions
dry_run_mode: true
policy:
  catastrophic:
    delete_without_where: BLOCK
    drop_table: BLOCK
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config = SafeQueryConfig.from_yaml(f.name)

        assert config.dialect == "mysql"
        assert "accounts" in config.protected_tables
        assert config.dry_run_mode is True
        assert config.policy.delete_without_where == "BLOCK"


class TestDictConfig:
    def test_from_dict(self):
        config = SafeQueryConfig.from_dict({
            "dialect": "postgres",
            "protected_tables": ["users"],
            "dry_run_mode": False,
        })
        assert config.dialect == "postgres"
        assert config.protected_tables == ["users"]
