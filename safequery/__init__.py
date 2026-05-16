"""SafeQuery - Stop catastrophic SQL before it executes."""

__version__ = "0.1.0"

from safequery.models import CheckResult
from safequery.core import SafeQuery

__all__ = ["SafeQuery", "CheckResult"]
