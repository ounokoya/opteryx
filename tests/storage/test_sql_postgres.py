"""
Test we can read from Sqlite - this is a basic exercise of the SQL Connector
"""

import os
import sys
import time

sys.path.insert(1, os.path.join(sys.path[0], "../.."))

import opteryx
from opteryx.connectors import SqlConnector
from tests.tools import is_arm, is_mac, is_version, is_windows, skip_if

POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
POSTGRES_USER = os.environ.get("POSTGRES_USER")


# limit contention on very low spec resources
@skip_if(is_arm() or is_mac() or is_windows() or not is_version("3.10"))
def test_postgres_storage():
    opteryx.register_store(
        "pg",
        SqlConnector,
        remove_prefix=True,
        connection=f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@trumpet.db.elephantsql.com/{POSTGRES_USER}",
    )

    t = time.monotonic_ns()
    results = opteryx.query("SELECT * FROM pg.planets")
    assert results.rowcount == 9, results.rowcount
    assert results.columncount == 20
    print((time.monotonic_ns() - t) / 1e9)
    t = time.monotonic_ns()

    # PROCESS THE DATA IN SOME WAY
    results = opteryx.query("SELECT COUNT(*) FROM pg.planets;")
    assert results.rowcount == 1, results.rowcount
    assert results.columncount == 1
    print((time.monotonic_ns() - t) / 1e9)
    t = time.monotonic_ns()

    # PUSH A PROJECTION
    results = opteryx.query("SELECT name FROM pg.planets;")
    assert results.rowcount == 9, results.rowcount
    assert results.columncount == 1
    print((time.monotonic_ns() - t) / 1e9)
    t = time.monotonic_ns()

    # JOIN ON A NON SQL TABLE
    results = opteryx.query(
        "SELECT * FROM pg.planets INNER JOIN $satellites ON pg.planets.id = $satellites.planetId;"
    )
    assert results.rowcount == 177, results.rowcount
    assert results.columncount == 28, results.columncount
    print((time.monotonic_ns() - t) / 1e9)
    t = time.monotonic_ns()

    # PUSH - CHECK STATS THE PUSHES WORKED
    results = opteryx.query("SELECT name FROM pg.planets WHERE name LIKE 'Earth';")
    assert results.rowcount == 1, results.rowcount
    assert results.columncount == 1
    assert results.stats["rows_read"] == 1
    assert results.stats["columns_read"] == 1
    print((time.monotonic_ns() - t) / 1e9)
    t = time.monotonic_ns()

    results = opteryx.query("SELECT * FROM pg.planets WHERE id > gravity")
    assert results.rowcount == 2, results.rowcount
    assert results.stats.get("rows_read", 0) == 9, results.stats
    print((time.monotonic_ns() - t) / 1e9)
    t = time.monotonic_ns()


if __name__ == "__main__":  # pragma: no cover
    from tests.tools import run_tests

    run_tests()
