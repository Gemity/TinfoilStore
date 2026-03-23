---
artifact_type: design
artifact_version: 1
run_id: run-20260323-032347-7909cac2
iteration: 1
phase: designing
phase_attempt: 1
producer: codex
created_at: 2026-03-23T03:23:47+07:00
design_version: 1
status: approved
---

# Objective

Introduce the first working backend service for the Tinfoil shop into this repository as a new Python application package, with enough structure to support user accounts, subscription-aware access control, and Wasabi-backed protected content delivery without disturbing the existing HiveMind orchestrator code.

# Scope

This iteration adds a separate backend application, not a replacement of the orchestrator runtime. The backend should expose a minimal HTTP API for health checks, authentication, current-user lookup, admin user management, admin subscription management, protected content listing, and subscription-gated download access. It should include persistent data models for users, subscriptions, subscription events, and content metadata, plus configuration and service layers for storage and authorization.

The backend should support the following business behavior in the first version:

- create and manage users
- authenticate users and issue bearer tokens
- evaluate subscription state as `active`, `expired`, or `revoked`
- record manual subscription extensions through an auditable admin action
- deny protected content access when the effective subscription state is not valid
- generate Wasabi S3-compatible presigned download URLs for authorized users

# Constraints

- The repository currently contains orchestrator runtime code only, so the backend must be introduced as a new package with clear separation from `orchestrator/`.
- The design must stay aligned with the HiveMind workflow: Codex produces design and review artifacts, Claude implements against this design.
- The first increment should be production-oriented but small. It must establish a maintainable service skeleton rather than attempt full Tinfoil protocol coverage.
- Wasabi integration must use standard S3-compatible configuration from environment variables: endpoint, region, bucket, access key, and secret key.
- Subscription logic must explicitly support `active`, `expired`, `revoked`, and manual extension flows.
- The design should avoid one-off scripts and favor clear module boundaries, migrations, and testable services.
- Python 3.10 is the current project baseline, so chosen libraries and structure should remain compatible with that runtime.

# Architecture

The repository should keep `orchestrator/` unchanged and add a sibling package, `shop_backend/`, as the application boundary. Recommended structure:

```text
shop_backend/
  app.py
  config.py
  api/
    deps.py
    routes/
      health.py
      auth.py
      users.py
      subscriptions.py
      content.py
      admin.py
  db/
    base.py
    session.py
    models.py
    migrations/
  schemas/
    auth.py
    users.py
    subscriptions.py
    content.py
  services/
    auth_service.py
    user_service.py
    subscription_service.py
    content_service.py
  storage/
    wasabi.py
  security/
    password.py
    tokens.py
tests/
  backend/
```

The service stack should be:

- FastAPI for the HTTP service layer
- SQLAlchemy 2.x for ORM and persistence
- Alembic for migrations
- PostgreSQL as the primary database target
- `boto3` for Wasabi S3-compatible access
- Argon2 or bcrypt-based password hashing
- JWT bearer tokens for the first authentication mechanism

Core data model:

- `users`: `id`, `username`, `email`, `password_hash`, `role`, `is_active`, `created_at`, `updated_at`
- `subscriptions`: `id`, `user_id`, `status`, `starts_at`, `ends_at`, `revoked_at`, `revoked_reason`, `created_at`, `updated_at`
- `subscription_events`: `id`, `subscription_id`, `event_type`, `effective_at`, `delta_days`, `notes`, `actor_user_id`, `created_at`
- `content_objects`: `id`, `title`, `storage_key`, `bucket_override`, `mime_type`, `size_bytes`, `sha256`, `is_protected`, `is_enabled`, `created_at`, `updated_at`

Subscription state is derived by the service layer using both stored status and timestamps:

- `revoked` if `subscriptions.status == revoked`
- `expired` if not revoked and `ends_at < now`
- `active` if not revoked and `starts_at <= now <= ends_at`

Manual extensions must update `subscriptions.ends_at` and append a `subscription_events` row with `event_type=manual_extension`. That keeps the current state query simple while preserving an audit trail.

Request flow for protected content:

1. Client authenticates and receives a bearer token.
2. Protected endpoints load the user and current subscription state from the database.
3. If the user is inactive, missing, expired, or revoked, the request returns `403`.
4. If authorized, the backend returns content metadata and, for downloads, a short-lived Wasabi presigned URL generated from `storage_key`.

Configuration should be environment-driven through a single settings module. Minimum variables:

- `DATABASE_URL`
- `APP_ENV`
- `JWT_SECRET_KEY`
- `JWT_ACCESS_TOKEN_TTL_MINUTES`
- `WASABI_ACCESS_KEY_ID`
- `WASABI_SECRET_ACCESS_KEY`
- `WASABI_BUCKET`
- `WASABI_REGION`
- `WASABI_ENDPOINT_URL`
- `WASABI_PRESIGN_TTL_SECONDS`

Initial endpoint set:

- `GET /healthz`
- `POST /auth/login`
- `GET /me`
- `POST /admin/users`
- `GET /admin/users/{user_id}`
- `POST /admin/subscriptions/{user_id}/grant`
- `POST /admin/subscriptions/{user_id}/extend`
- `POST /admin/subscriptions/{user_id}/revoke`
- `GET /content`
- `GET /content/{content_id}/download`

This is intentionally a generic shop foundation. Tinfoil-specific response shapes and shop protocol endpoints can be layered later on top of the same auth, subscription, and storage services.

# Execution Plan

1. Update `pyproject.toml` to add backend runtime dependencies and define a backend entrypoint while preserving the existing orchestrator script.
2. Create the `shop_backend/` package with app factory, config loading, route registration, database session wiring, and a health endpoint.
3. Add SQLAlchemy models and Alembic migration scaffolding for `users`, `subscriptions`, `subscription_events`, and `content_objects`.
4. Implement authentication primitives: password hashing, token issuance, current-user dependency, and `POST /auth/login`.
5. Implement admin user and subscription services, including grant, revoke, and manual extension flows with event logging.
6. Implement Wasabi storage adapter and protected content services that gate list and download access on effective subscription validity.
7. Add backend tests for auth, subscription state transitions, access denial, manual extension handling, and storage URL generation behavior.

# Acceptance Criteria

- The repository contains a new backend application package in addition to the orchestrator runtime.
- The backend starts successfully and serves at least `GET /healthz`.
- User, subscription, subscription event, and content metadata models exist with migrations or equivalent schema creation support.
- A user can authenticate and retrieve identity information through authenticated API access.
- Admin flows can grant, extend, and revoke subscriptions, and manual extensions are recorded in an audit-friendly form.
- Protected content endpoints reject users with missing, expired, or revoked subscriptions.
- Authorized protected content download requests return a short-lived Wasabi presigned URL.
- Wasabi connection settings are fully environment-driven and S3-compatible.
- Tests cover the critical subscription gating rules and the main happy path for authenticated protected access.

# Non-Goals

- Full Nintendo Switch Tinfoil shop protocol implementation
- Frontend or admin web UI
- Payment provider integration or automated billing
- Multi-tenant shop support
- Background workers, analytics, or notification pipelines
- Complex token revocation/session management beyond short-lived bearer tokens
