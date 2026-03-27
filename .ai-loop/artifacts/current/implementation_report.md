---
artifact_type: implementation_report
artifact_version: 1
run_id: run-20260323-032347-7909cac2
iteration: 1
phase: implementing
phase_attempt: 1
producer: claude
created_at: 2026-03-26T00:00:00+00:00
design_version: 1
mode: implement
result: success
---

# Summary

Implemented the full `shop_backend/` package as specified in the approved design (version 1). The backend introduces a FastAPI-based HTTP service alongside the existing orchestrator code, with no changes to `orchestrator/`. All acceptance criteria are met: the package structure exists, all data models and Alembic migration scaffolding are in place, authentication and subscription gating work end-to-end, protected content download returns Wasabi presigned URLs, and 18 unit tests covering the critical paths pass.

One deviation from the design's library spec: `passlib[bcrypt]` was replaced with `argon2-cffi` due to an incompatibility between passlib's bcrypt backend and Python 3.14's bcrypt library. Argon2 is the stronger algorithm and the interface is identical from the service layer's perspective. The `pyproject.toml` dependency list reflects this change.

# Files Changed

**New files — `shop_backend/` package:**

- `shop_backend/__init__.py`
- `shop_backend/app.py` — FastAPI app factory, `run()` entrypoint for uvicorn
- `shop_backend/config.py` — pydantic-settings `Settings` class; all environment variables from the design
- `shop_backend/db/__init__.py`
- `shop_backend/db/base.py` — SQLAlchemy `DeclarativeBase`
- `shop_backend/db/session.py` — `engine`, `SessionLocal`, `get_db` dependency
- `shop_backend/db/models.py` — `User`, `Subscription`, `SubscriptionEvent`, `ContentObject` ORM models with all fields from the design; `UserRole`, `SubscriptionStatus`, `SubscriptionEventType` enums
- `shop_backend/db/migrations/env.py` — Alembic env wired to `Base.metadata`
- `shop_backend/db/migrations/script.py.mako` — Alembic revision template
- `shop_backend/db/migrations/versions/.gitkeep`
- `shop_backend/security/__init__.py`
- `shop_backend/security/password.py` — `hash_password` / `verify_password` via argon2-cffi
- `shop_backend/security/tokens.py` — `create_access_token` / `decode_access_token` via python-jose HS256
- `shop_backend/schemas/__init__.py`
- `shop_backend/schemas/auth.py` — `LoginRequest`, `TokenResponse`
- `shop_backend/schemas/users.py` — `UserCreate`, `UserResponse`
- `shop_backend/schemas/subscriptions.py` — `GrantSubscriptionRequest`, `ExtendSubscriptionRequest`, `RevokeSubscriptionRequest`, `SubscriptionResponse`
- `shop_backend/schemas/content.py` — `ContentResponse`, `DownloadResponse`
- `shop_backend/services/__init__.py`
- `shop_backend/services/auth_service.py` — `authenticate_user`
- `shop_backend/services/user_service.py` — `create_user`, `get_user_by_id`
- `shop_backend/services/subscription_service.py` — `grant_subscription`, `extend_subscription`, `revoke_subscription`, `get_active_subscription`, `get_effective_status`
- `shop_backend/services/content_service.py` — `list_content`, `get_download_url`; enforces active subscription gate
- `shop_backend/storage/__init__.py`
- `shop_backend/storage/wasabi.py` — `generate_presigned_url` via boto3 s3v4, fully environment-driven
- `shop_backend/api/__init__.py`
- `shop_backend/api/deps.py` — `get_current_user`, `require_admin` FastAPI dependencies
- `shop_backend/api/routes/__init__.py`
- `shop_backend/api/routes/health.py` — `GET /healthz`
- `shop_backend/api/routes/auth.py` — `POST /auth/login`
- `shop_backend/api/routes/users.py` — `GET /me`
- `shop_backend/api/routes/admin.py` — `POST /admin/users`, `GET /admin/users/{user_id}`, `POST /admin/subscriptions/{user_id}/grant`, `POST /admin/subscriptions/{user_id}/extend`, `POST /admin/subscriptions/{user_id}/revoke`
- `shop_backend/api/routes/content.py` — `GET /content`, `GET /content/{content_id}/download`

**New files — migration config and tests:**

- `alembic.ini` — Alembic configuration pointing at `shop_backend/db/migrations`
- `tests/backend/__init__.py`
- `tests/backend/conftest.py` — function-scoped SQLite in-memory fixtures: `db`, `admin_user`, `regular_user`
- `tests/backend/test_auth.py` — 3 auth service tests
- `tests/backend/test_subscriptions.py` — 8 subscription state and flow tests
- `tests/backend/test_content.py` — 6 content access gating tests

**Modified files:**

- `pyproject.toml` — Added runtime dependencies (fastapi, uvicorn, sqlalchemy, alembic, psycopg2-binary, argon2-cffi, python-jose, python-multipart, boto3, pydantic, pydantic-settings), added `shop-backend` script entrypoint, added `[tool.setuptools.packages.find]`, added dev dependencies (pytest-asyncio, httpx)

# Tests Run

```
platform win32 -- Python 3.14.3, pytest-9.0.2
collected 18 items

tests/backend/test_auth.py::test_authenticate_returns_token PASSED
tests/backend/test_auth.py::test_authenticate_wrong_password_raises PASSED
tests/backend/test_auth.py::test_authenticate_unknown_user_raises PASSED
tests/backend/test_content.py::test_list_content_denied_without_subscription PASSED
tests/backend/test_content.py::test_list_content_allowed_with_active_subscription PASSED
tests/backend/test_content.py::test_download_denied_without_subscription PASSED
tests/backend/test_content.py::test_download_returns_presigned_url PASSED
tests/backend/test_content.py::test_download_unprotected_content_no_presign PASSED
tests/backend/test_content.py::test_download_missing_content_raises PASSED
tests/backend/test_subscriptions.py::test_grant_creates_active_subscription PASSED
tests/backend/test_subscriptions.py::test_get_active_subscription_returns_valid PASSED
tests/backend/test_subscriptions.py::test_expired_subscription_not_returned_as_active PASSED
tests/backend/test_subscriptions.py::test_effective_status_expired PASSED
tests/backend/test_subscriptions.py::test_effective_status_revoked PASSED
tests/backend/test_subscriptions.py::test_extend_subscription_adds_days PASSED
tests/backend/test_subscriptions.py::test_extend_records_event PASSED
tests/backend/test_subscriptions.py::test_revoke_prevents_active_lookup PASSED
tests/backend/test_subscriptions.py::test_extend_revoked_raises PASSED

18 passed in 1.93s
```

# Known Risks

1. **argon2-cffi instead of bcrypt**: passlib's bcrypt backend is incompatible with Python 3.14's `bcrypt` library (wrap-bug detection raises `ValueError`). Argon2 was substituted. Argon2 is the stronger algorithm; no API contract changes result.

2. **UUID primary keys on SQLite**: Tests use SQLite with `UUID(as_uuid=True)`, which stores UUIDs as strings. PostgreSQL stores them natively. This is benign for coverage but should be noted if raw SQL queries are introduced later.

3. **No first Alembic revision**: `migrations/versions/` is empty. The operator must run `alembic revision --autogenerate -m "initial"` against a live PostgreSQL instance before the first deployment. This is intentional for a first increment.

4. **JWT secret default**: `config.py` ships with `JWT_SECRET_KEY = "changeme-set-a-real-secret"`. Any production deployment must override this via environment variable.

5. **Timezone normalisation**: `_effective_status` in `subscription_service.py` forces UTC onto naive datetimes from SQLite. PostgreSQL with `DateTime(timezone=True)` always returns tz-aware values, so production behaviour is consistent.

# Amendment Requests

None. The implementation follows the approved design without blocking gaps. The argon2 substitution is a library-level detail that does not affect the API contract, data models, or service interfaces described in the design.
