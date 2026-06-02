from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime

import asyncpg

from api.core.database import db
from api.models.schemas import AuthenticatedUserResponse

PBKDF2_ITERATIONS = 600_000
PBKDF2_ALGORITHM = "sha256"
ADMIN_LOGIN_NAME = "admin"
ADMIN_EMAIL = "admin@prompcorp.local"
ADMIN_NAME = "Administrator"
ADMIN_PASSWORD = "admin"


class AuthError(Exception):
    """Base authentication exception."""


class InvalidCredentialsError(AuthError):
    """Raised when a login attempt fails."""


class DuplicateEmailError(AuthError):
    """Raised when a registration email already exists."""


class InvalidEmailError(AuthError):
    """Raised when a registration email is invalid."""


class InvalidNameError(AuthError):
    """Raised when a registration name is invalid."""


@dataclass(slots=True)
class AuthRecord:
    user: AuthenticatedUserResponse
    password_hash: str


class AuthService:
    async def ensure_schema(self) -> None:
        assert db.pool is not None
        async with db.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                  name TEXT NOT NULL,
                  email TEXT NOT NULL,
                  login_name TEXT,
                  password_hash TEXT NOT NULL,
                  is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                """
                ALTER TABLE users
                  ADD COLUMN IF NOT EXISTS login_name TEXT,
                  ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                """
            )
            await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users (email)")
            await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_login_name ON users (login_name)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_created_at ON users (created_at DESC)")
        await self.ensure_admin_user()

    async def ensure_admin_user(self) -> None:
        assert db.pool is not None
        password_hash = self.hash_password(ADMIN_PASSWORD)
        async with db.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (name, email, login_name, password_hash, is_admin)
                VALUES ($1, $2, $3, $4, TRUE)
                ON CONFLICT (login_name) DO UPDATE SET
                  name = EXCLUDED.name,
                  email = EXCLUDED.email,
                  password_hash = EXCLUDED.password_hash,
                  is_admin = TRUE,
                  updated_at = NOW()
                """,
                ADMIN_NAME,
                ADMIN_EMAIL,
                ADMIN_LOGIN_NAME,
                password_hash,
            )

    async def create_user(self, *, name: str, email: str, password: str) -> AuthenticatedUserResponse:
        normalized_name = name.strip()
        if not normalized_name:
            raise InvalidNameError("Please enter the user's name.")
        normalized_email = self.normalize_email(email)
        if "@" not in normalized_email or normalized_email.startswith("@") or normalized_email.endswith("@"):
            raise InvalidEmailError("Please enter a valid email address.")

        password_hash = self.hash_password(password)
        assert db.pool is not None

        try:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO users (name, email, password_hash, is_admin)
                    VALUES ($1, $2, $3, FALSE)
                    RETURNING id, name, email, login_name, is_admin, created_at
                    """,
                    normalized_name,
                    normalized_email,
                    password_hash,
                )
        except asyncpg.UniqueViolationError as exc:
            raise DuplicateEmailError("That email is already registered.") from exc

        assert row is not None
        return self._row_to_user(row)

    async def authenticate(self, *, identifier: str, password: str) -> AuthenticatedUserResponse:
        normalized_identifier = identifier.strip().lower()
        if not normalized_identifier or not password:
            raise InvalidCredentialsError("Email and password are required.")

        record = await self.get_auth_record(normalized_identifier)
        if record is None or not self.verify_password(password, record.password_hash):
            raise InvalidCredentialsError("Invalid email or password.")
        return record.user

    async def get_user_by_id(self, user_id: str) -> AuthenticatedUserResponse | None:
        assert db.pool is not None
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, name, email, login_name, is_admin, created_at
                FROM users
                WHERE id = $1
                """,
                user_id,
            )
        return self._row_to_user(row) if row else None

    async def get_auth_record(self, identifier: str) -> AuthRecord | None:
        assert db.pool is not None
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, name, email, login_name, is_admin, created_at, password_hash
                FROM users
                WHERE email = $1 OR login_name = $1
                """,
                identifier,
            )
        if row is None:
            return None
        return AuthRecord(
            user=self._row_to_user(row),
            password_hash=row["password_hash"],
        )

    def normalize_email(self, email: str) -> str:
        return email.strip().lower()

    def hash_password(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        derived = hashlib.pbkdf2_hmac(PBKDF2_ALGORITHM, password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        return "$".join(
            [
                "pbkdf2_sha256",
                str(PBKDF2_ITERATIONS),
                base64.b64encode(salt).decode("ascii"),
                base64.b64encode(derived).decode("ascii"),
            ]
        )

    def verify_password(self, password: str, encoded: str) -> bool:
        try:
            algorithm, iterations_text, salt_b64, hash_b64 = encoded.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            salt = base64.b64decode(salt_b64.encode("ascii"))
            expected = base64.b64decode(hash_b64.encode("ascii"))
            derived = hashlib.pbkdf2_hmac(
                PBKDF2_ALGORITHM,
                password.encode("utf-8"),
                salt,
                int(iterations_text),
            )
        except (ValueError, binascii.Error):
            return False
        return hmac.compare_digest(derived, expected)

    def _row_to_user(self, row: asyncpg.Record) -> AuthenticatedUserResponse:
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return AuthenticatedUserResponse(
            id=str(row["id"]),
            name=str(row["name"]),
            email=str(row["email"]),
            login_name=row["login_name"],
            is_admin=bool(row["is_admin"]),
            created_at=created_at,
        )
