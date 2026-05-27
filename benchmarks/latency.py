"""Measure SafeQuery.check() latency. Run: python benchmarks/latency.py

Reports mean / p50 / p99 / max over a mix of representative queries.
"""

import statistics
import time

from safequery import SafeQuery

QUERIES = [
    "DELETE FROM users",
    "SELECT id, name FROM users WHERE id = 42",
    "UPDATE accounts SET balance = 0 WHERE id = 2",
    "DROP TABLE temp_imports",
    "SELECT * FROM a JOIN b ON a.id = b.id WHERE a.created_at > '2024-01-01'",
    "DELETE FROM logs WHERE created_at < '2020-01-01' AND level = 'debug'",
]


def main(iterations: int = 2000) -> None:
    sq = SafeQuery()
    for q in QUERIES:  # warm up
        sq.check(q)

    times_ms = []
    for _ in range(iterations):
        for q in QUERIES:
            start = time.perf_counter()
            sq.check(q)
            times_ms.append((time.perf_counter() - start) * 1000)

    times_ms.sort()
    n = len(times_ms)
    print(f"samples : {n}")
    print(f"mean    : {statistics.mean(times_ms):.3f} ms")
    print(f"p50     : {times_ms[n // 2]:.3f} ms")
    print(f"p99     : {times_ms[int(n * 0.99)]:.3f} ms")
    print(f"max     : {times_ms[-1]:.3f} ms")


if __name__ == "__main__":
    main()
