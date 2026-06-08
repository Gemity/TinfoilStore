# TinfoilStore - Deployment & Operations Guide

## VPS Server

| Item | Value |
|------|-------|
| IP | 180.93.35.196 |
| OS | Ubuntu 24.04 LTS |
| Timezone | Asia/Ho_Chi_Minh (UTC+7) |
| SSH | `ssh root@180.93.35.196` |
| App path | `/opt/tinfoilstore/` |
| Python venv | `/opt/tinfoilstore/venv/` |
| Nginx config | `/etc/nginx/sites-available/tinfoilstore` |
| Systemd service | `/etc/systemd/system/tinfoilstore.service` |

## Current Production State

- Backend is running on VPS through `systemd + uvicorn`.
- Nginx proxies `:80 -> 127.0.0.1:8000`.
- Database is PostgreSQL 16 on the same VPS.
- Game files are stored on Wasabi.
- Tinfoil icons/banners are now cached locally on the VPS.
- Shop feed returns local asset URLs and local download redirect URLs.

## Service Commands

```bash
# Service status
ssh root@180.93.35.196 "systemctl status tinfoilstore --no-pager"

# Restart backend
ssh root@180.93.35.196 "systemctl restart tinfoilstore"

# Live logs
ssh root@180.93.35.196 "journalctl -u tinfoilstore -f"

# Recent logs
ssh root@180.93.35.196 "journalctl -u tinfoilstore --no-pager -n 100"
```

## Deploy Code

```bash
cd "D:\AI Project\TinfoilStore"
scp -r shop_backend root@180.93.35.196:/opt/tinfoilstore/
ssh root@180.93.35.196 "systemctl restart tinfoilstore"
```

## Database

| Item | Value |
|------|-------|
| Engine | PostgreSQL 16 |
| Host | localhost:5432 |
| DB name | tinfoilstore |
| User | postgres |
| Password | tinfoilstore_db_pass |

```bash
# Open DB shell on VPS
ssh root@180.93.35.196 "sudo -u postgres psql tinfoilstore"

# Run migration
ssh root@180.93.35.196 "cd /opt/tinfoilstore && source venv/bin/activate && python -m alembic upgrade head"
```

## Wasabi CDN

| Item | Value |
|------|-------|
| Bucket | tinfoil-server |
| Region | ap-southeast-1 |
| Endpoint | https://s3.ap-southeast-1.wasabisys.com |
| Credentials | Stored in `/opt/tinfoilstore/.env` |

## Sync Games

```bash
# Scan bucket and insert new games into DB
ssh root@180.93.35.196 "cd /opt/tinfoilstore && source venv/bin/activate && python -m shop_backend.sync_content"

# Scan only a prefix
ssh root@180.93.35.196 "cd /opt/tinfoilstore && source venv/bin/activate && python -m shop_backend.sync_content --prefix games/"

# Scan and remove DB items deleted from Wasabi
ssh root@180.93.35.196 "cd /opt/tinfoilstore && source venv/bin/activate && python -m shop_backend.sync_content --cleanup"
```

## TitleDB And Local Icon Cache

TitleDB provides metadata such as icon, banner, publisher, and description.

Current behavior:

- Backend reads metadata from `/opt/tinfoilstore/titledb.json`
- Backend caches icon/banner files locally on disk
- Tinfoil downloads icons from the VPS, not directly from Nintendo CDN
- This avoids client-side icon failures when Nintendo domains are blocked by `90DNS` or DNS MITM

Local cache paths:

- `/opt/tinfoilstore/asset_cache/iconUrl/`
- `/opt/tinfoilstore/asset_cache/bannerUrl/`

Example cached files:

- `/opt/tinfoilstore/asset_cache/iconUrl/0100CD801CE5E000.jpg`
- `/opt/tinfoilstore/asset_cache/bannerUrl/0100CD801CE5E000.jpg`

Refresh TitleDB:

```bash
ssh root@180.93.35.196 "curl -sL 'https://raw.githubusercontent.com/blawar/titledb/master/US.en.json' -o /opt/tinfoilstore/titledb.json && systemctl restart tinfoilstore"
```

Warm local icon/banner cache for current games:

```bash
ssh root@180.93.35.196 "cd /opt/tinfoilstore && source venv/bin/activate && python - <<'PY'
from shop_backend.db.session import SessionLocal
from shop_backend.services.shop_service import cache_titledb_assets_for_content

db = SessionLocal()
print(cache_titledb_assets_for_content(db))
PY"
```

Expected output example:

```text
{'titles': 1, 'iconUrl': 1, 'bannerUrl': 1}
```

## Tinfoil Feed Behavior

Important runtime behavior:

- `GET /shop/` returns Tinfoil shop index
- File URLs now use local route format:
  - `/shop/download/{content_id}/{filename}`
- Icon URLs now use local route format:
  - `/shop/assets/icon/{title_id}`
- Banner URLs now use local route format:
  - `/shop/assets/banner/{title_id}`
- `/shop/download/...` authenticates user, then redirects to a fresh Wasabi presigned URL

This means:

- client sees stable local URLs
- title parsing is easier for Tinfoil
- icon fetching no longer depends on Nintendo domains from the Switch

## Create Admin User

```bash
ssh root@180.93.35.196 "cd /opt/tinfoilstore && source venv/bin/activate && python -m shop_backend.create_admin --username admin --email admin@example.com --password matkhau123"
```

## Tinfoil Switch Config

```text
Protocol: http
Host:     180.93.35.196
Port:     80
Path:     /shop/
Username: (username)
Password: (password)
Title:    TinfoilStore
Enabled:  YES
```

Notes:

- Use a plain display label for `Title`, for example `TinfoilStore`
- Do not put `admin:password@host` inside the `Title` field
- On Tinfoil, icon/cover art is visible in grid/icon view, not table-only view

## API Endpoints

Admin endpoints support both Basic Auth and Bearer Token.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /healthz | - | Health check |
| POST | /auth/login | - | Login and receive JWT |
| GET | /me | Bearer/Basic | Current user |
| GET | /admin/users | Admin | List users |
| POST | /admin/users | Admin | Create user |
| GET | /admin/users/{id} | Admin | User detail |
| POST | /admin/subscriptions/{id}/grant | Admin | Grant subscription |
| POST | /admin/subscriptions/{id}/extend | Admin | Extend subscription |
| POST | /admin/subscriptions/{id}/revoke | Admin | Revoke subscription |
| GET | /admin/content | Admin | List content |
| POST | /admin/content | Admin | Create content |
| PATCH | /admin/content/{id} | Admin | Update content |
| DELETE | /admin/content/{id} | Admin | Delete content |
| GET | /content | Bearer/Basic | Game list |
| GET | /content/{id}/download | Bearer/Basic | Presigned download URL |
| GET | /shop/ | Basic Auth | Tinfoil shop index |
| GET | /shop/assets/icon/{title_id} | Public via shop feed | Local cached icon |
| GET | /shop/assets/banner/{title_id} | Public via shop feed | Local cached banner |
| GET | /shop/download/{content_id}/{filename} | Basic Auth | Redirect to Wasabi |
| GET | /docs | - | Swagger docs |

## Subscription Format

```json
{"days": 30, "hours": 0, "minutes": 0}
{"days": 0, "hours": 2, "minutes": 0}
{"days": 0, "hours": 0, "minutes": 5}
{"days": 1, "hours": 6, "minutes": 30}
```

## Nginx

```text
Client:80 -> Nginx -> 127.0.0.1:8000 (uvicorn)
```

```bash
ssh root@180.93.35.196 "nginx -t"
ssh root@180.93.35.196 "systemctl restart nginx"
```

## Systemd Service File

Path: `/etc/systemd/system/tinfoilstore.service`

```ini
[Unit]
Description=TinfoilStore Backend
After=network.target postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tinfoilstore
ExecStart=/opt/tinfoilstore/venv/bin/uvicorn shop_backend.app:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Environment File

VPS path: `/opt/tinfoilstore/.env`
Local path: `D:\AI Project\TinfoilStore\.env`

```env
APP_ENV=production
DATABASE_URL=postgresql://postgres:tinfoilstore_db_pass@localhost:5432/tinfoilstore
JWT_SECRET_KEY=<auto-generated>
JWT_ACCESS_TOKEN_TTL_MINUTES=60
WASABI_ACCESS_KEY_ID=<key>
WASABI_SECRET_ACCESS_KEY=<secret>
WASABI_BUCKET=tinfoil-server
WASABI_REGION=ap-southeast-1
WASABI_ENDPOINT_URL=https://s3.ap-southeast-1.wasabisys.com
WASABI_PRESIGN_TTL_SECONDS=300
```

## Quick Admin Flow

1. Open `http://180.93.35.196/docs`
2. Authorize with admin account
3. `POST /admin/users`
4. Copy returned `id`
5. `POST /admin/subscriptions/{user_id}/grant`
6. Send Tinfoil shop credentials to the user

## Common Errors

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | OK |
| 201 | Created | OK |
| 401 | Not authenticated | Re-check Basic Auth or login |
| 403 | Forbidden | Check admin role or active subscription |
| 404 | Not found | Verify user id, content id, or title id |
| 409 | Conflict | Username/email already exists |
| 422 | Validation error | Check request JSON |
