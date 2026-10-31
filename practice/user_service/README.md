# user_service

A minimal FastAPI + PostgreSQL user service used to demonstrate the full
schema → API → tests → docs pipeline.

```
practice/user_service/
├── schema.sql     # Idempotent PostgreSQL DDL (users table + trigger)
├── db.py          # Connection + schema-application helpers
├── main.py        # FastAPI app with CRUD endpoints
├── test_api.py    # pytest suite covering the API endpoints
└── README.md      # This document
```

## Architecture

- **Backend:** FastAPI
- **Primary database:** PostgreSQL
- **Deployment:** Kubernetes (all internal services run on Kubernetes)

A short-lived PostgreSQL connection is opened per request via
`db.connection_from_env()`, configured with `DATABASE_URL` (Kubernetes
Secret convention) or the individual `PG*` environment variables
(`PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`).

## Database schema

`schema.sql` defines the `users` table:

| Column          | Type             | Notes                                        |
|-----------------|------------------|----------------------------------------------|
| `id`            | `BIGSERIAL`      | Primary key                                  |
| `name`          | `VARCHAR(120)`   | Required                                     |
| `email`         | `VARCHAR(320)`   | Required, unique                             |
| `password_hash` | `TEXT`           | Nullable                                     |
| `active`        | `BOOLEAN`        | Defaults to `TRUE`; indexed                  |
| `created_at`    | `TIMESTAMPTZ`    | Defaults to `now()`                          |
| `updated_at`    | `TIMESTAMPTZ`    | Defaults to `now()`; refreshed by a trigger  |

Design notes:

- **Idempotent DDL** — every statement uses `IF NOT EXISTS` (or drops the
  trigger before recreating it), so `apply_schema()` can run at every
  startup without error.
- **Case-insensitive email uniqueness** — a unique index on `lower(email)`
  rejects `Alice@app.io` alongside `alice@app.io`.
- **`updated_at` trigger** — the `set_updated_at()` function + the
  `trg_users_set_updated_at` trigger automatically refresh `updated_at`
  on any `UPDATE`.

## API endpoints

All request/response bodies are validated with Pydantic. Errors follow the
FastAPI convention (`{"detail": "..."}`).

| Method   | Path              | Description                                        |
|----------|-------------------|----------------------------------------------------|
| `GET`    | `/health`         | Liveness check with a live DB round-trip           |
| `GET`    | `/users`          | List users (`?active=true/false`, `?limit=N`)      |
| `GET`    | `/users/{id}`     | Get a single user, `404` if absent                 |
| `POST`   | `/users`          | Create a user, `201`; `409` on duplicate email     |
| `PATCH`  | `/users/{id}`     | Partial update; `400` if empty, `404` if missing   |
| `DELETE` | `/users/{id}`     | Delete a user, always `204` (idempotent)           |

The app applies the schema on startup via a FastAPI `lifespan` handler, so
deploying a fresh container automatically provisions the tables.

## Setup

The provided schema is a plain SQL file and the code only requires a
PostgreSQL 14+ server — no ORM or migration tooling is involved.

```bash
# 1. Dependencies
pip install fastapi "psycopg[binary]" pydantic[email] uvicorn

# 2. Point at a PostgreSQL database (either form works)
export DATABASE_URL=postgresql://postgres:secret@127.0.0.1:5432/user_service
# or
export PGHOST=127.0.0.1 PGPORT=5432 PGUSER=postgres \
       PGPASSWORD=secret PGDATABASE=user_service

# 3. Run the API (schema auto-applies on startup)
uvicorn practice.user_service.main:app
```

For local development against Docker:

```bash
docker run -d --name user_service_pg -e POSTGRES_DB=user_service \
  -e POSTGRES_PASSWORD=testpw -p 15432:5432 postgres:16

export PGHOST=127.0.0.1 PGPORT=15432 PGUSER=postgres \
       PGPASSWORD=testpw PGDATABASE=user_service
```

## Tests

```bash
PGHOST=127.0.0.1 PGPORT=15432 PGUSER=postgres \
PGPASSWORD=testpw PGDATABASE=user_service \
pytest practice/user_service/test_api.py
```

Each test truncates the `users` table first, so the suite is hermetic and
re-runnable.

## Kubernetes deployment notes

- Pass the DSN through a Secret as `DATABASE_URL`.
- Startup applies `schema.sql` automatically; no init container needed.
- The app is stateless — scale horizontally with multiple replicas; the DB
  connection pool in Kubernetes is handled by the database at the network
  layer, so per-request short-lived connections are sufficient for this
  reference service.
