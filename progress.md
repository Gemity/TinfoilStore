# TinfoilStore Progress Snapshot

Last updated: 2026-06-20

## 🔴 SECURITY INCIDENT & SERVER MIGRATION (2026-06-20)

The old production VPS (azvps.vn, `160.187.229.43`) was found **fully compromised (rooted)** and is being abandoned. Migration to a new clean VPS is in progress.

### What happened
- The azvps VPS was **backdoored from the provisioning image** (supply-chain). From first boot (2026-05-19 23:02) it already had: a rogue `node` user with `NOPASSWD:ALL` sudo, attacker SSH key `ElPatrono1337` (in `/home/node` and `/root`), and SSH-botnet malware in `/var/tmp/15767cda/` (cron every minute, fake `myservices.service` → `/usr/bin/ssshd`).
- A rogue app-admin `you_got_pwned_by_IvY` (DB user, created 2026-05-23) was a symptom, NOT the entry vector. The default `admin/admin123` was NOT the root cause.
- Entry vector = the poisoned image (attacker SSHed as `node`, sudo → root). `.bash_history` cleared. Logs only go back to 2026-05-24 so the initial event isn't logged.

### Actions taken
- **Wasabi keys rotated.** Old key `N179FJW7K8HNJF8FC43Z` is compromised (must be deleted in Wasabi console — CONFIRM). New key is in `env/shop2.env` (gitignored): `J9UUALHVXOUZ4F0GCZUE`.
- **Bucket scanned clean** (via local boto3, new key works): 6108 objects / ~685 GB, 217 game files + 5825 Việt-hoá files; no foreign/executable files injected. No need to recreate the bucket — keeping `tinfoil-store`.
- **New VPS provisioned: LANIT, `103.149.86.18`, Ubuntu 24.04 LTS**, 1 vCPU / ~1GB RAM / 24GB disk. New SSH key `tinfoil_vps_ed25519` (ed25519) at `C:\Users\PC\.ssh\`. First-boot audit = CLEAN.
- **Stage 1 hardening done on new VPS:** 2GB swap added, `ufw` firewall (allow 22/80/2121/30000-30100), SSH hardened (`PasswordAuthentication no`, `PermitRootLogin prohibit-password` — key-only login verified), full `apt upgrade`.

### ⚠️ OPEN / PENDING — CUSTOMER DATA RECOVERY (CRITICAL)
- **Customer data was NOT exported before the old server went offline.** The PostgreSQL DB `tinfoilstore` (FTP users, subscriptions, expiry dates) and the FTP user list exist ONLY on the old azvps server's disk — no backup elsewhere.
- Old server `160.187.229.43` is currently **unreachable** (ping/SSH timeout). User cannot access the azvps panel yet (as of 2026-06-20).
- **TODO when azvps access returns:** check if the VPS still exists (powered-off = recoverable) or was deleted. If recoverable: power on briefly, `pg_dump tinfoilstore` + `getent group tinfoilftp`, copy the text dumps to a clean machine, then destroy it. Boot = malware runs again, so be quick / isolate.
- Even if recovered, **all customer FTP passwords must be reset** (the box's `/etc/shadow` was exposed). The only truly valuable thing to recover = the list of customers + their subscription expiry dates.
- If unrecoverable: rebuild customer list from payment/sales records.

### Stage 2 — FTP-only deploy on new LANIT VPS — DONE (2026-06-20)
- New server fully provisioned and validated end-to-end on `103.149.86.18` (Ubuntu 24.04):
  - rclone mount of `wasabi:tinfoil-store` (new key) → `/srv/tinfoil-unified` unified root (218 entries incl. `viet-hoa`, Z-A titleids correct).
  - vsftpd on port 2121 (passive 30000-30100, `pasv_address=103.149.86.18`); external FTP login verified (218 files visible).
  - PostgreSQL 16 DB `tinfoilstore`, FastAPI/uvicorn :8000 behind nginx :80; `/healthz`, `/docs`, `/admin/content`, `/admin/admins` all 200.
  - 4 new admin-management endpoints deployed and working. New admin created with a STRONG password (NOT admin123).
- The FTP-only provisioning scripts were reconstructed and **saved to `deploy/ftp-only/`** (services, start/stop scripts, vsftpd.conf, rclone template, README) so they are no longer lost.
- Gotchas captured in `deploy/ftp-only/README.md`: FUSE `user_allow_other`, and the `/etc/shells` + `nologin` fix (else vsftpd gives "530 Login incorrect").
- Secrets for the new server are recorded in `env/shop2.env` (gitignored): DB password, JWT secret, new Wasabi key, `VPS_IP=103.149.86.18`. New admin password: see the deploy session / change it via `/admin/admins`.

### Remaining to fully cut over
- ⚠️ **Customer data recovery from old offline azvps server still PENDING** (see open item above) — the new DB has only the fresh `admin`, no customer FTP users/subscriptions yet.
- Confirm old Wasabi key `N179FJW7K8HNJF8FC43Z` is deleted in the Wasabi console.
- Give customers the new Tinfoil FTP config: host `103.149.86.18`, port `2121`, path `/`, their FTP user/password (passwords must be re-issued).
- Old server `160.187.229.43` to be destroyed once data is recovered.

## Current Status

- Project has moved past the HiveMind AI workflow phase and is now treated as a live product backend.
- Repository has been cleaned to focus on the live TinfoilStore backend.
- HiveMind/orchestrator workflow files were removed in commit `796aa96`.
- A pre-cleanup checkpoint exists at commit `1d0be8a`.
- Local branch is `main`; latest local commit is pushed to `origin/main`.
- Current operator guide is `ADMIN_GUIDE_SHOP_v5.docx` (v4 retained as previous snapshot).

## Git State

- Current branch: `main`
- Latest commit: `82897f6 Update FTP shop admin docs and endpoints`
- Cleanup commit: `796aa96 Remove obsolete HiveMind workflow files`
- Previous checkpoint: `1d0be8a Checkpoint live TinfoilStore state before cleanup`
- Remote `origin/main`: `82897f6 Update FTP shop admin docs and endpoints`
- Working tree: contains uncommitted FTP-only revert, stale-mount hardening, previous hybrid experiments, tests, and this progress update.
- Push status: pushed to GitHub `origin/main`.

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
|-- ADMIN_GUIDE_SHOP_v4.docx
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
- HTTP shop `/shop/`: disabled again for the FTP-only configuration; live check after deploy returned `404`.
- Removed old HTTP-shop endpoints from the mounted live app:
  - `/auth/login` now returns `404`
  - `/content` now returns `404`
  - `/me` now returns `404`
- Current final design: FTP-only. `/shop/` is not mounted; folder/path browsing and Việt hóa files are served through FTP.
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
  - `POST /admin/sync` now runs hybrid sync: refreshes FTP root, syncs Wasabi game files into the HTTP shop index DB, cleans stale DB entries by default, and warms TitleDB assets.
- OpenAPI now exposes `/healthz`, FTP user administration, FTP-user subscription administration, `GET /admin/content`, and `POST /admin/sync`.
- `GET /admin/ftp-users` now returns operator-focused fields only: `username`, `ftp_active`, `subscription_status`, `ends_at`, `days_remaining`, and `revoked_reason`.
- FTP port `2121`: open.
- FTP banner previously confirmed as `vsFTPd 3.0.5`.
- Server 2 focus: FTP-only Tinfoil setup. FTP `2121` supplies File Browser with folder paths and Việt hóa files. `New Games` is not expected from FTP.
- 2026-06-09 content incident: `Pokemon Legends Z-A` did not appear correctly after sync because two Wasabi object names used the DLC TitleID `0100F43008C45002` for base/update content and the update file had no `.nsp` extension. Fixed live Wasabi names to:
  - `Pokemon Legends Z-A [0100F43008C44000][v0].nsp`
  - `Pokemon Legends Z-A [0100F43008C44000][v262144].nsp`
  - Kept DLC as `Pokemon Legends Z-A [0100F43008C45002][v0][DLC 2].nsp`
  - Refreshed `tinfoil-wasabi-mount` and `tinfoil-ftp-unified-root`; `/admin/content?max_items=5000` now returns all three Z-A files.

## Final Tinfoil Config

Current decision: use only the FTP source. The operator will rename/fix the problematic Pokémon file/folder names on Wasabi/FTP side.

### FTP Source

```text
Protocol: ftp
Host:     160.187.229.43
Port:     2121
Path:     /
Username: FTP user
Password: FTP password
Title:    Tinfoil Store
```

Important: remove any older HTTP `/shop/` source from Tinfoil to avoid stale cached index behavior.

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
- `ADMIN_GUIDE_SHOP_v4.docx`
- `progress.md`

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
- 2026-06-09 hybrid deploy verification:
  - `/shop/`: mounted again and returns `401` without HTTP Basic credentials, expected.
  - `POST /admin/sync?cleanup=true`: `200`, added the corrected `Pokemon Legends Z-A` base/update entries and removed stale Z-A DB rows.
  - Internal shop index for active user `TranTruongSon`: returns 176 files and includes all three Z-A entries.
- 2026-06-10 HTTP root verification:
  - Initial attempt used `build_mixed_root_index`, which returned installable files plus `directories: [".../shop/folder/viet-hoa/"]`.
  - This did make Việt hóa visible over HTTP, but it caused later Tinfoil crawl/freeze problems and was reverted.
- 2026-06-10 Tinfoil follow-up fix:
  - Tinfoil requested `/shop/folder/viet-hoa/` and `/shop/file/...` without repeating HTTP Basic Auth, causing `401` on child URLs.
  - `/shop/` still requires Basic Auth, but generated child file/folder URLs now include a short-lived `access_token` query string.
  - Public test with an active user confirmed `/shop/` returns 176 files, the `viet-hoa/` directory opens without Basic Auth, and a `Pokemon Legends Z-A` file URL redirects to Wasabi successfully.
- 2026-06-10 bad referrer fix:
  - Removed optional `referrer` from HTTP shop JSON responses because Tinfoil reported `bad referrer` when following child file/folder URLs.
  - Public test confirmed root and folder JSON no longer include `referrer`; `viet-hoa/` and a `Pokemon Legends Z-A` file URL still work.
- 2026-06-10 popup fix:
  - Removed `success: "Browsing ..."` from folder/subfolder JSON responses because Tinfoil shows the `success` field as a modal popup on every folder browse.
  - Root `/shop/` still has one welcome message, but `/shop/folder/...` responses no longer include `success`.
- 2026-06-10 Tinfoil freeze fix:
  - HTTP `/shop/` root was changed back to a flat DB-backed shop index with `directories: []`.
  - Reason: Tinfoil aggressively crawled the HTTP `viet-hoa/` directory tree, causing too many requests/popups and user-side freezes when opening File Browser.
  - HTTP `/shop/` is now for `New Games` only; FTP remains the supported File Browser source for folder/path browsing and Việt hóa files.
  - HTTP download URLs now include short-lived `access_token` query strings so Tinfoil can download child `/shop/download/...` URLs without repeating Basic Auth.
  - Public test confirmed `/shop/` has no `referrer`, no directories, 176 files, and all three `Pokemon Legends Z-A` entries; a Z-A download URL redirects to Wasabi successfully.
- 2026-06-11 FTP-only revert:
  - User decided to return to FTP-only and manually rename/fix the problematic Pokémon file/folder names.
  - `shop_backend.app` no longer mounts `/shop`; live check returned `/shop/` as `404`.
  - `/admin/sync` was changed back to FTP-only behavior: it refreshes `tinfoil-wasabi-mount` and `tinfoil-ftp-unified-root`; it no longer syncs the HTTP content DB or warms TitleDB assets.
  - Local `ftp_index_service.list_ftp_content` was hardened to skip stale/broken mount entries and report them in `errors` instead of crashing `/admin/content` with `500`.
  - Live `/admin/content` briefly returned `500` because `/srv/tinfoil-unified` had stale bind mounts: `OSError [Errno 107] Transport endpoint is not connected`. Restarting the Wasabi/FTP root services is needed to clear stale mounts if this appears again.

- 2026-06-16 stale-mount incident (Tinfoil only saw 6 files):
  - Symptom: Tinfoil FTP console showed `6 files loaded` instead of ~200; also `could not parse title id from filename (causes slow boot)` warnings.
  - Root cause: cascade FUSE failure. Base rclone mount `/mnt/tinfoil-wasabi` dropped ("transport endpoint is not connected"). `tinfoil-wasabi-mount.service` then crash-looped because it could not remount over the dead mountpoint. `tinfoil-ftp-unified-root.service` had been `failed` since 2026-06-11 because its cleanup `find ... -delete` hit `Device or resource busy` on the 227 per-file bind mounts (script uses `set -euo pipefail`).
  - All ~227 per-file `mount --bind` entries under `/srv/tinfoil-unified` (and 176 under `/srv/tinfoil-ftp/games`) were stale.
  - Recovery performed: `systemctl stop` both services → lazy-unmount all 353 stale child binds (paths have spaces/`[]`, so iterate via python decoding `/proc/mounts`, deepest-first, `umount -l`) → `fusermount -uz` + `umount -l /mnt/tinfoil-wasabi` → `systemctl start tinfoil-wasabi-mount` (62 root entries) → `systemctl start tinfoil-ftp-unified-root` (rebuilt 205 binds, 0 transport errors).
  - Verified: `GET /admin/content` returns 204 game files + `viet-hoa` directory, no errors; `POST /admin/sync` returns both services `active`.
  - Architectural risk: the per-file bind-mount design cascades to total failure whenever the base rclone mount drops. Consider a recovery wrapper / systemd ordering so unified-root force-cleans stale binds before rebuilding, and/or rclone auto-reconnect hardening.
- 2026-06-16 Z-A New Games fix:
  - CORRECTION: the earlier claim "Tinfoil does not build New Games from FTP" is WRONG. In practice all games DO appear in Tinfoil New Games over the FTP source; only Pokemon Z-A was missing.
  - Root cause: the Z-A update file carried the BASE TitleID. On Wasabi `Pokemon Z-A/` had `[0100F43008C44000][v0]` (4.33 GB base) AND `[0100F43008C44000][v262144]` (2.12 GB update) — the update reused the base id (`...44000`) instead of the update id (`...44800`). Tinfoil saw the base title id at two versions (v0 + v262144), could not reconcile a "base at v262144", and dropped Z-A from the New Games grid.
  - File sizes confirmed which is which: base 4.33 GB, update 2.12 GB (a Switch 2 full edition would be ~4GB+, so the 2.12 GB file is a patch). DLC `[0100F43008C45002][v0][DLC 2]` is only 121 KB — likely a broken/placeholder file, still to be fixed.
  - Fix: renamed update on Wasabi to `Pokemon Legends Z-A [0100F43008C44800][v262144].nsp` (base id `...44000` -> update id `...44800`). Base `[v0]` and DLC unchanged. (Operator did the rclone moveto manually because the agent's auto-mode classifier blocks production storage writes.)
  - Refresh procedure after a Wasabi rename: stop unified-root -> lazy-unmount all binds -> `systemctl restart tinfoil-wasabi-mount` (clears rclone's 30m dir cache) -> start unified-root. Restart of the base mount is REQUIRED for renames to show, because the mount runs `--dir-cache-time 30m --poll-interval 0`.
  - Verified: `/admin/content` lists base + update + DLC with corrected ids; 204 game files; `/admin/sync` returns both services active.

## Tinfoil Issues Encountered

- FTP-only source solved File Browser and Việt hóa path visibility, but Tinfoil does not build `New Games` from FTP directory listing.
- HTTP `/shop/` DB-only index solved `New Games`, but did not show Việt hóa folders because it returned `directories: []`.
- HTTP mixed root with `viet-hoa/` folder made Việt hóa visible, but Tinfoil did not repeat HTTP Basic Auth for child `/shop/folder/...` and `/shop/file/...` URLs, causing `401` responses.
- Adding short-lived `access_token` to child URLs fixed the `401` issue.
- Tinfoil then reported `bad referrer`; removing optional `referrer` from HTTP shop JSON fixed that issue.
- Folder responses included `success: "Browsing ..."`, which Tinfoil displayed as modal popups for every folder/subfolder; removing `success` from folder JSON fixed the popup storm.
- Even after the above fixes, HTTP folder browsing caused Tinfoil to aggressively crawl the deep Việt hóa tree and freeze the client.
- Final decision as of 2026-06-11: disable HTTP `/shop/` again and use FTP as the only supported Tinfoil source.

## Notes And Risks

- `.env` and `env/` are ignored by Git and were not committed.
- `ADMIN_GUIDE_SHOP_v4.docx` is the current operator guide for the FTP-based live shop.
- `ADMIN_GUIDE_SHOP_v3.docx` is retained only as the previous guide snapshot and contains obsolete HTTP-shop workflow references.
- HTTP shop code remains in the repository for reference/fallback, but `/shop/` is not mounted in the FTP-only live app.
- FTP user management remains available through `/admin/ftp-users`.
- `GET /admin/ftp-users` supports partial username search, so operators do not need to enter the exact username for lookup.
- `POST /admin/sync` is FTP-only again and does not update the HTTP content DB.
- Current live FTP users may have mixed home directories; this should be checked before creating many more accounts.

## Next Steps

1. Rename/fix the Pokémon Z-A public-facing folder/file names to ASCII where needed, especially `Pokémon` -> `Pokemon`.
2. Run `POST /admin/sync` after Wasabi/file rename to refresh the FTP root.
3. Verify server 2 FTP listing with a real FTP user credential in Tinfoil File Browser.
4. If `/admin/content` shows stale mount errors, restart `tinfoil-wasabi-mount` and `tinfoil-ftp-unified-root`.
5. Commit and push the FTP-only revert and progress update when ready.
