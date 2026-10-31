"""FastAPI application for the user_service.

Endpoints in this module read/write the ``users`` table defined in
``schema.sql``. Every request opens a short-lived PostgreSQL connection via
``db.connection_from_env()`` (configured through ``DATABASE_URL`` or the
``PG*`` environment variables), so the app can be deployed as a plain
container on Kubernetes without extra setup.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response, status
from psycopg import Connection
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .db import apply_schema, connection_from_env


# -- Pydantic models ---------------------------------------------------------


class UserIn(BaseModel):
    """Payload for creating a user."""

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr = Field(max_length=320)
    password_hash: str | None = None
    active: bool = True


class UserUpdate(BaseModel):
    """Optional fields for partially updating a user."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = Field(default=None, max_length=320)
    password_hash: str | None = None
    active: bool | None = None


class UserOut(BaseModel):
    """Serialized representation of a user row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    password_hash: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


# -- Database helpers --------------------------------------------------------


def _get_connection() -> Connection:
    """Build the PostgreSQL connection used by the current request."""
    return connection_from_env()


def _fetch_user(conn: Connection, user_id: int) -> tuple | None:
    """Return the ``users`` row for ``user_id``, or ``None`` if absent."""
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name, email, password_hash, active, created_at, updated_at
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )
        return cursor.fetchone()


def _row_to_user(row: tuple) -> UserOut:
    """Convert a ``users`` row into a validated ``UserOut``."""
    return UserOut(
        id=row[0],
        name=row[1],
        email=row[2],
        password_hash=row[3],
        active=row[4],
        created_at=row[5],
        updated_at=row[6],
    )


# -- Application --------------------------------------------------------------


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Apply the schema on startup and yield control to the app."""
    with connection_from_env() as conn:
        apply_schema(conn)
    yield


app = FastAPI(title="User Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    """Return service health, including a live database round-trip."""
    with _get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    return {"status": "ok"}


@app.get("/users", response_model=list[UserOut])
def list_users(
    active: bool | None = Query(
        default=None, description="Filter by the active status flag"
    ),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[tuple]:
    """List users, optionally filtered by their active status."""
    query = """
        SELECT id, name, email, password_hash, active, created_at, updated_at
        FROM users
    """
    params: list = []
    if active is not None:
        query += " WHERE active = %s"
        params.append(active)
    query += " ORDER BY id LIMIT %s"
    params.append(limit)

    with _get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return [_row_to_user(row) for row in cursor.fetchall()]


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int) -> UserOut:
    """Return a single user by id, or 404 when it does not exist."""
    with _get_connection() as conn:
        row = _fetch_user(conn, user_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return _row_to_user(row)


@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserIn) -> UserOut:
    """Create a user and return the stored row."""
    with _get_connection() as conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (name, email, password_hash, active)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, name, email, password_hash, active,
                              created_at, updated_at
                    """,
                    (payload.name, payload.email, payload.password_hash, payload.active),
                )
                row = cursor.fetchone()
            conn.commit()
        except UniqueViolation:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )
        return _row_to_user(row)


@app.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate) -> UserOut:
    """Update provided fields of a user (partial update)."""
    fields: dict[str, object] = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    assignments = ", ".join(f"{name} = %s" for name in fields)
    values = [*fields.values(), user_id]

    with _get_connection() as conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE users
                    SET {assignments}
                    WHERE id = %s
                    RETURNING id, name, email, password_hash, active,
                              created_at, updated_at
                    """,
                    values,
                )
                row = cursor.fetchone()
                if row is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found",
                    )
            conn.commit()
        except UniqueViolation:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )
        return _row_to_user(row)


@app.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_user(user_id: int) -> None:
    """Delete a user; returns 204 even if the user did not exist (idempotent)."""
    with _get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
    return None
