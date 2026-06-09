# TinfoilStore Progress Snapshot

Last updated: 2026-06-09

## Current Status

- Project has moved past the HiveMind AI workflow phase and is now treated as a live product backend.
- Repository has been cleaned to focus on the live TinfoilStore backend.
- HiveMind/orchestrator workflow files were removed in commit `d653ea1`.
- A pre-cleanup checkpoint exists at commit `563daa1`.
- Local branch is `main`; latest local commit is ahead of `origin/main`.

## Git State

- Current branch: `main`
- Latest commit: `d653ea1 Remove obsolete HiveMind workflow files`
- Previous checkpoint: `563daa1 Checkpoint live TinfoilStore state before cleanup`
- Remote `origin/main`: `fbfe1f1 update Hivemind AI`
- Working tree: contains uncommitted local documentation/backend changes after the server 2 endpoint cleanup.
- Not pushed yet.

## Remaining Project Structure

```text
TinfoilStore/
|-- deploy/
|-- env/
|   |-- shop1.env
|   `-- shop2.env
|-- shop_backend/
|-- tests/
|   `-- backend/
|-- .env
|-- .gitignore
|-- ADMIN_GUIDE_SHOP_v3.docx
|-- alembic.ini
|-- progress.md
`-- pyproject.toml
```

## Backend Package

- Main app package: `shop_backend/`
- App entrypoint: `shop_backend.app:app`
- Console script: `shop-backend`
- Package metadata now uses `tinfoilstore-backend`.
- `ENABLE_HTTP_SHOP` defaults to `False`; HTTP shop routes are not active unless explicitly enabled.

## Server 2 Live State

- Server: `160.187.229.43`
- Admin docs: `http://160.187.229.43/docs`
- Health endpoint: `http://160.187.229.43/healthz`
- Health check result: `200 {"status":"ok"}`
- HTTP shop `/shop/`: returns `404`, expected after moving away from HTTP shop.
- Removed old HTTP-shop endpoints from the mounted live app:
  - `/auth/login` now returns `404`
  - `/content` now returns `404`
  - `/me` now returns `404`
  - `/shop/` remains `404`
- Removed DB-user subscription endpoints from the operator surface:
  - `/admin/users` now returns `404`
  - `/admin/users/search` now returns `404`
  - `/admin/subscriptions/{user_id}/...` now returns `404`
- Kept FTP administration endpoints mounted, now with subscription info:
  - `/admin/ftp-users` with optional partial `username` search
  - `/admin/ftp-users/{username}`
- Added subscription endpoints by FTP username:
  - `POST /admin/ftp-users/{username}/subscription/grant`
  - `POST /admin/ftp-users/{username}/subscription/extend`
  - `POST /admin/ftp-users/{username}/subscription/revoke`
- Reused familiar operator endpoints for FTP shop:
  - `GET /admin/content` now lists the FTP root at `/srv/tinfoil-unified`
  - `POST /admin/sync` now refreshes the FTP index by restarting `tinfoil-wasabi-mount` and `tinfoil-ftp-unified-root`
- OpenAPI now exposes `/healthz`, FTP user administration, FTP-user subscription administration, `GET /admin/content`, and `POST /admin/sync`.
- `GET /admin/ftp-users` now returns operator-focused fields only: `username`, `ftp_active`, `subscription_status`, `ends_at`, `days_remaining`, and `revoked_reason`.
- FTP port `2121`: open.
- FTP banner previously confirmed as `vsFTPd 3.0.5`.
- Server 2 focus: FTP-based Tinfoil file browser so folder paths and Vietnamese localization files can appear as filesystem paths rather than flat HTTP shop entries.

## Server 2 Tinfoil Config

```text
Protocol: ftp
Host:     160.187.229.43
Port:     2121
Path:     /
Username: FTP user
Password: FTP password
Title:    Tinfoil Store
```

## Cleanup Completed

Removed obsolete/non-live files:

- HiveMind workflow workspace: `.ai-loop/`
- Orchestrator runtime package: `orchestrator/`
- HiveMind submodule: `HiveMind-AI/`
- HiveMind skills/templates: `skills/`, `template_prompts/`
- Old progress/runtime docs: `.process`, `orchestrator_runtime_spec.md`, `HIVEMIND_TEMPLATE_README.md`
- Old generated guides and investigation docs.
- Old HTTP shop snapshot: `shop_index.json`
- Icon DB build artifacts and helper script.
- Orchestrator-only tests.

Kept live/product files:

- `shop_backend/`
- `deploy/`
- `env/`
- `.env`
- `alembic.ini`
- `tests/backend/`
- `ADMIN_GUIDE_SHOP_v3.docx`

## Validation

- Backend tests command: `py -m pytest -q tests/backend`
- Result: `19 passed`
- Server 2 deploy verification:
  - `/healthz`: `200`
  - `/docs`: `200`
  - OpenAPI paths: `/healthz`, `/admin/content`, `/admin/sync`, `/admin/ftp-users`, `/admin/ftp-users/{username}`, `/admin/ftp-users/{username}/subscription/grant`, `/admin/ftp-users/{username}/subscription/extend`, `/admin/ftp-users/{username}/subscription/revoke`
  - old HTTP-shop endpoints: `404`
  - `POST /admin/sync`: `200`, refreshed FTP index successfully
  - FTP `2121`: open

## Notes And Risks

- `.env` and `env/` are ignored by Git and were not committed.
- `ADMIN_GUIDE_SHOP_v4.docx` is the current operator guide for the FTP-based live shop.
- `ADMIN_GUIDE_SHOP_v3.docx` is retained only as the previous guide snapshot and contains obsolete HTTP-shop workflow references.
- If HTTP shop is never needed again, `shop_backend/api/routes/shop.py` and `shop_backend/services/shop_service.py` can be reviewed later for possible removal.
- FTP user management remains available through `/admin/ftp-users`.
- `GET /admin/ftp-users` supports partial username search, so operators do not need to enter the exact username for lookup.
- `POST /admin/sync` is intentionally kept as a familiar operator action, but it no longer syncs the HTTP content DB.
- Current live FTP users may have mixed home directories; this should be checked before creating many more accounts.

## Next Steps

1. Review `ADMIN_GUIDE_SHOP_v4.docx` with the operator before replacing or archiving v3.
2. Push commits `563daa1` and `d653ea1` to GitHub when ready.
3. Verify server 2 FTP listing with a real FTP user credential.
4. If desired, add a fresh Markdown guide for FTP operations so the project does not rely only on `.docx`.
5. Commit the server 2 FTP endpoint remapping changes when ready.
