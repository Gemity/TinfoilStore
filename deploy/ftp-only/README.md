# TinfoilStore — FTP-only deployment (clean VPS)

Provisioning for the FTP-only shop on a fresh Ubuntu 24.04 VPS. These are the
server-side scripts that previously lived only on the (now decommissioned) server.

Architecture: rclone mounts the Wasabi bucket read-only → a per-file bind-mount
script flattens it into `/srv/tinfoil-unified` → vsftpd (port 2121) serves that
dir to chrooted FTP users → FastAPI/uvicorn behind nginx provides the `/docs`
admin panel. Game files live on Wasabi; the VPS only relays.

## Files here
- `tinfoil-wasabi-mount.service` → `/etc/systemd/system/` — rclone mount of `wasabi:tinfoil-store` at `/mnt/tinfoil-wasabi`.
- `tinfoil-ftp-unified-root-start` / `-stop` → `/usr/local/sbin/` (chmod +x) — flatten/cleanup the mount into `/srv/tinfoil-unified`. The `-stop` script is Python for robust unmounting (avoids the cascade stale-mount failure).
- `tinfoil-ftp-unified-root.service` → `/etc/systemd/system/`.
- `vsftpd.conf` → `/etc/vsftpd.conf` — **edit `pasv_address` to the server's public IP**.
- `rclone.conf.template` → `/root/.config/rclone/rclone.conf` (chmod 600) — fill in current Wasabi keys.

## Order of operations
1. Stage 1 hardening: 2GB swap, `ufw` (allow 22/80/2121/30000-30100), SSH key-only (`PasswordAuthentication no`, `PermitRootLogin prohibit-password`), `apt upgrade` + reboot.
2. `apt install -y rclone fuse3 vsftpd postgresql postgresql-contrib python3 python3-venv python3-pip nginx curl`.
3. rclone: write `/root/.config/rclone/rclone.conf` (from template, real keys), then `rclone lsd wasabi:tinfoil-store` to test.
4. **Enable FUSE allow_other**: `grep -q '^user_allow_other' /etc/fuse.conf || echo user_allow_other >> /etc/fuse.conf` (required for the mount's `--allow-other`).
5. Install + `systemctl enable --now tinfoil-wasabi-mount`; verify `ls /mnt/tinfoil-wasabi`.
6. Install scripts + `systemctl enable --now tinfoil-ftp-unified-root` (takes ~1-2 min for ~200 bind mounts); verify `ls /srv/tinfoil-unified` (no "Transport endpoint" errors).
7. vsftpd: copy config, `mkdir -p /var/run/vsftpd/empty`, `groupadd --system tinfoilftp`, restart vsftpd.
8. **`/etc/shells` fix (REQUIRED)**: FTP users get the `/usr/sbin/nologin` shell; vsftpd's `pam_shells` rejects shells not in `/etc/shells` → "530 Login incorrect". Add them: `for s in /usr/sbin/nologin /sbin/nologin /bin/false; do grep -qx "$s" /etc/shells || echo "$s" >> /etc/shells; done`.
9. App: PostgreSQL DB + strong password, `.env` (strong JWT, current Wasabi keys, `ENABLE_HTTP_SHOP=false`), venv + pip deps, `alembic upgrade head`, create admin with a **strong** password (never `admin123`), `tinfoilstore.service` (uvicorn :8000), nginx proxy 80→8000.

## Verify
- `curl http://IP/healthz` → 200; `http://IP/docs` → 200; `/admin/content` (admin basic-auth) lists the FTP root.
- External FTP: `FTP(IP:2121)` login as a created FTP user, passive mode, `nlst()` lists ~200 files + `viet-hoa`.

## Notes
- Per-file bind-mount design is fragile: if the base rclone mount drops, all binds go stale. The `-stop` script + `Requires=`/`After=` ordering mitigate it. After any Wasabi rename, restart `tinfoil-wasabi-mount` (its `--dir-cache-time 30m` caches listings) then the unified-root.
- FTP user/subscription management is via the `/docs` admin panel (`/admin/ftp-users`, `/admin/admins`). No SSH needed for day-to-day ops.
