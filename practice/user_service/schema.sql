-- user_service schema for PostgreSQL.
--
-- Idempotent by design: every statement uses IF NOT EXISTS (or DROP ... IF
-- EXISTS before CREATE), so apply_schema() can be run repeatedly without
-- errors. The primary database is PostgreSQL (project architecture); this
-- file contains no engine-specific workarounds for other databases.

CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    name          VARCHAR(120) NOT NULL,
    email         VARCHAR(320) NOT NULL,
    password_hash TEXT,
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE INDEX IF NOT EXISTS ix_users_active ON users (active);

-- Case-insensitive uniqueness: prevents "Alice@app.io" alongside
-- "alice@app.io" even though the exact-match CHECK would allow both.
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_ci ON users (lower(email));

-- Automatically refresh updated_at on any UPDATE.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_users_set_updated_at ON users;

CREATE TRIGGER trg_users_set_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
