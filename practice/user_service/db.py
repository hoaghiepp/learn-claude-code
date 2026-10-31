"""Database connection and schema management for the user_service.

Exposes a tiny, dependency-light API used by the FastAPI endpoints:

- ``connection_from_env()`` builds a psycopg connection from
  ``DATABASE_URL`` or individual ``PG*`` environment variables.
- ``apply_schema(conn)`` applies ``schema.sql`` idempotently (safe to run
  repeatedly, on every startup).
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
from psycopg import Connection

SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def connection_from_env(environment: dict[str, str] | None = None) -> Connection:
    """Build a PostgreSQL connection from the environment.

    Uses ``DATABASE_URL`` when set (production/Kubernetes convention),
    otherwise falls back to individual ``PGHOST`` / ``PGPORT`` / ``PGUSER`` /
    ``PGPASSWORD`` / ``PGDATABASE`` variables matching libpq's defaults.

    Args:
        environment: Mapping to read config from; defaults to ``os.environ``.

    Returns:
        A ready-to-use psycopg connection to PostgreSQL.
    """
    env = os.environ if environment is None else environment

    if dsn := env.get("DATABASE_URL"):
        return psycopg.connect(dsn)

    return psycopg.connect(
        host=env.get("PGHOST", "127.0.0.1"),
        port=env.get("PGPORT", "5432"),
        user=env.get("PGUSER", "postgres"),
        password=env.get("PGPASSWORD", ""),
        dbname=env.get("PGDATABASE", "user_service"),
    )


def apply_schema(conn: Connection) -> None:
    """Apply the PostgreSQL schema to ``conn`` idempotently.

    Every statement in ``schema.sql`` is written to be safe on repeat runs,
    so this may be called at application startup without version tracking.

    Args:
        conn: Open PostgreSQL connection to apply the schema on.
    """
    with conn.cursor() as cursor:
        cursor.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
    conn.commit()
