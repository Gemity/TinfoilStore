#!/bin/bash
# TinfoilStore - Deploy to fresh VPS
#
# Usage:
#   bash deploy.sh <VPS_IP> <WASABI_KEY> <WASABI_SECRET> <WASABI_BUCKET> [SSH_USER=root]
#
# Example:
#   bash deploy.sh 103.45.67.89 MYACCESSKEY mysecretkey my-bucket-name

set -e

VPS_IP="${1:?Usage: bash deploy.sh <VPS_IP> <WASABI_KEY> <WASABI_SECRET> <WASABI_BUCKET> [SSH_USER]}"
WASABI_KEY="${2:?Missing WASABI_ACCESS_KEY_ID}"
WASABI_SECRET="${3:?Missing WASABI_SECRET_ACCESS_KEY}"
WASABI_BUCKET="${4:?Missing WASABI_BUCKET}"
SSH_USER="${5:-root}"

DB_PASS="$(openssl rand -hex 16)"
JWT_SECRET="$(openssl rand -hex 32)"
SSH="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 ${SSH_USER}@${VPS_IP}"

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== TinfoilStore Deploy ==="
echo "VPS: ${SSH_USER}@${VPS_IP}"
echo "Bucket: ${WASABI_BUCKET}"
echo ""

# 1. Install packages
echo "[1/8] Installing packages..."
$SSH "apt update -qq && apt install -y -qq python3 python3-pip python3-venv postgresql postgresql-contrib nginx curl > /dev/null 2>&1 && echo 'OK'"

# 2. Setup PostgreSQL
echo "[2/8] Setting up PostgreSQL..."
$SSH "sudo -u postgres psql -c \"CREATE DATABASE tinfoilstore;\" 2>/dev/null || true && \
      sudo -u postgres psql -c \"ALTER USER postgres PASSWORD '${DB_PASS}';\" && echo 'OK'"

# 3. Upload code
echo "[3/8] Uploading code..."
$SSH "mkdir -p /opt/tinfoilstore"
scp -r "${PROJECT_DIR}/shop_backend" "${SSH_USER}@${VPS_IP}:/opt/tinfoilstore/"
scp "${PROJECT_DIR}/alembic.ini" "${SSH_USER}@${VPS_IP}:/opt/tinfoilstore/"

# 4. Create .env
echo "[4/8] Creating .env..."
$SSH "cat > /opt/tinfoilstore/.env << EOF
APP_ENV=production
DATABASE_URL=postgresql://postgres:${DB_PASS}@localhost:5432/tinfoilstore
JWT_SECRET_KEY=${JWT_SECRET}
JWT_ACCESS_TOKEN_TTL_MINUTES=60
WASABI_ACCESS_KEY_ID=${WASABI_KEY}
WASABI_SECRET_ACCESS_KEY=${WASABI_SECRET}
WASABI_BUCKET=${WASABI_BUCKET}
WASABI_REGION=ap-southeast-1
WASABI_ENDPOINT_URL=https://s3.ap-southeast-1.wasabisys.com
WASABI_PRESIGN_TTL_SECONDS=300
EOF"

# 5. Setup venv
echo "[5/8] Setting up Python venv..."
$SSH "cd /opt/tinfoilstore && python3 -m venv venv && source venv/bin/activate && \
      pip install --quiet fastapi uvicorn sqlalchemy psycopg2-binary alembic \
      pydantic-settings email-validator argon2-cffi 'python-jose[cryptography]' boto3 pillow python-multipart && echo 'OK'"

# 6. Migrations + admin
echo "[6/8] Running migrations..."
$SSH "cd /opt/tinfoilstore && source venv/bin/activate && \
      python -m alembic upgrade head && \
      python -m shop_backend.create_admin --username admin --email admin@tinfoilstore.local --password admin123 && echo 'OK'"

# 7. Nginx
echo "[7/8] Configuring nginx..."
$SSH 'cat > /etc/nginx/sites-available/tinfoilstore << "NGINX"
server {
    listen 80;
    server_name _;
    client_max_body_size 0;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/tinfoilstore /etc/nginx/sites-enabled/tinfoilstore
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx'

# 8. Systemd
echo "[8/8] Setting up systemd service..."
$SSH 'cat > /etc/systemd/system/tinfoilstore.service << "SVC"
[Unit]
Description=TinfoilStore Backend
After=network.target postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tinfoilstore
EnvironmentFile=/opt/tinfoilstore/.env
ExecStart=/opt/tinfoilstore/venv/bin/uvicorn shop_backend.app:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVC
systemctl daemon-reload && systemctl enable tinfoilstore && systemctl start tinfoilstore'

# Post-deploy
echo "[+] Syncing content & TitleDB..."
$SSH "cd /opt/tinfoilstore && source venv/bin/activate && python -m shop_backend.sync_content" || true
$SSH "curl -sL 'https://raw.githubusercontent.com/blawar/titledb/master/US.en.json' -o /opt/tinfoilstore/titledb.json" || true

echo ""
echo "=== DONE ==="
echo ""
echo "Server:  http://${VPS_IP}"
echo "Docs:    http://${VPS_IP}/docs"
echo "Admin:   admin / admin123"
echo ""
echo "Tinfoil config cho user:"
echo "  Protocol: http"
echo "  Host:     ${VPS_IP}"
echo "  Port:     80"
echo "  Path:     /shop/"
echo ""
echo "--- LƯU LẠI ---"
echo "DB Password:  ${DB_PASS}"
echo "JWT Secret:   ${JWT_SECRET}"
