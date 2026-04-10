#!/usr/bin/env bash
set -euo pipefail

#=============================================================================
# Configuration
#=============================================================================
DOMAIN="nihargupte.com"
REPO="https://github.com/nihargupte-ph/nihar-website.git"
DEPLOY_USER="deploy"
DEPLOY_HOME="/home/${DEPLOY_USER}"
PROJECT_DIR="${DEPLOY_HOME}/nihar-website"
MAMBA_ROOT="${DEPLOY_HOME}/micromamba"
CERTBOT_EMAIL="gupten8@gmail.com"

echo "=== Nihar Website Server Provisioning ==="
echo "Domain: ${DOMAIN}"
echo "Project directory: ${PROJECT_DIR}"
echo ""

#=============================================================================
# Step 1: System packages
#=============================================================================
echo "[1/11] Installing system packages..."
apt-get update
apt-get install -y \
    build-essential \
    nginx \
    certbot python3-certbot-nginx \
    git git-lfs \
    ufw \
    curl \
    bzip2

git lfs install --system

#=============================================================================
# Step 2: Create deploy user
#=============================================================================
echo "[2/11] Setting up deploy user..."
if ! id "${DEPLOY_USER}" &>/dev/null; then
    adduser --disabled-password --gecos "" "${DEPLOY_USER}"
    usermod -aG www-data "${DEPLOY_USER}"
fi

# Allow deploy user to restart gunicorn and reload nginx without password
cat > /etc/sudoers.d/deploy-gunicorn <<'SUDOERS'
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart gunicorn-nihar
deploy ALL=(ALL) NOPASSWD: /bin/systemctl reload nginx
SUDOERS
chmod 440 /etc/sudoers.d/deploy-gunicorn

#=============================================================================
# Step 3: SSH key setup for deploy user
#=============================================================================
echo "[3/11] Setting up SSH access for deploy user..."
mkdir -p "${DEPLOY_HOME}/.ssh"
if [ -f /root/.ssh/authorized_keys ]; then
    cp /root/.ssh/authorized_keys "${DEPLOY_HOME}/.ssh/authorized_keys"
fi
chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${DEPLOY_HOME}/.ssh"
chmod 700 "${DEPLOY_HOME}/.ssh"
chmod 600 "${DEPLOY_HOME}/.ssh/authorized_keys" 2>/dev/null || true

#=============================================================================
# Step 4: Install micromamba
#=============================================================================
echo "[4/11] Installing micromamba..."
if [ ! -f "${MAMBA_ROOT}/bin/micromamba" ]; then
    sudo -u "${DEPLOY_USER}" mkdir -p "${MAMBA_ROOT}"
    curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | \
        sudo -u "${DEPLOY_USER}" tar -xvj -C "${MAMBA_ROOT}" --strip-components=1 bin/micromamba
    echo "  micromamba installed"
else
    echo "  micromamba already installed"
fi

#=============================================================================
# Step 5: Clone repository
#=============================================================================
echo "[5/11] Cloning repository..."
if [ ! -d "${PROJECT_DIR}/.git" ]; then
    sudo -u "${DEPLOY_USER}" git clone "${REPO}" "${PROJECT_DIR}"
    cd "${PROJECT_DIR}"
    sudo -u "${DEPLOY_USER}" git lfs pull
else
    echo "  Repository already exists, pulling latest..."
    cd "${PROJECT_DIR}"
    sudo -u "${DEPLOY_USER}" git pull
    sudo -u "${DEPLOY_USER}" git lfs pull
fi

#=============================================================================
# Step 6: Create conda environment
#=============================================================================
echo "[6/11] Creating conda environment (this may take 5-10 minutes)..."
cd "${PROJECT_DIR}"
MAMBA="${MAMBA_ROOT}/bin/micromamba"

if [ ! -d "${MAMBA_ROOT}/envs/nihar-website" ]; then
    sudo -u "${DEPLOY_USER}" "${MAMBA}" create -y \
        -r "${MAMBA_ROOT}" \
        -f environment.yml
    echo "  Environment created"
else
    echo "  Environment already exists, updating..."
    sudo -u "${DEPLOY_USER}" "${MAMBA}" update -y \
        -r "${MAMBA_ROOT}" \
        -n nihar-website \
        -f environment.yml
fi

# Shortcut to the env's python/gunicorn
ENV_PYTHON="${MAMBA_ROOT}/envs/nihar-website/bin/python"
ENV_GUNICORN="${MAMBA_ROOT}/envs/nihar-website/bin/gunicorn"

# Verify key packages
echo "  Verifying packages..."
sudo -u "${DEPLOY_USER}" "${ENV_PYTHON}" -c "import django; import h5py; import pyseobnr; print('All packages OK')"

#=============================================================================
# Step 7: Create .env file
#=============================================================================
echo "[7/11] Creating .env file..."
ENV_FILE="${PROJECT_DIR}/.env"
if [ ! -f "${ENV_FILE}" ]; then
    SECRET_KEY=$(sudo -u "${DEPLOY_USER}" "${ENV_PYTHON}" -c \
        'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
    cat > "${ENV_FILE}" <<ENVEOF
SECRET_KEY=${SECRET_KEY}
DEBUG=False
ALLOWED_HOSTS=${DOMAIN},www.${DOMAIN}
ENVEOF
    chown "${DEPLOY_USER}:${DEPLOY_USER}" "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
    echo "  Created .env with new SECRET_KEY"
else
    echo "  .env already exists, skipping"
fi

#=============================================================================
# Step 8: Django setup
#=============================================================================
echo "[8/11] Running Django setup..."
cd "${PROJECT_DIR}"
sudo -u "${DEPLOY_USER}" mkdir -p logs media

sudo -u "${DEPLOY_USER}" "${ENV_PYTHON}" manage.py collectstatic --noinput
sudo -u "${DEPLOY_USER}" "${ENV_PYTHON}" manage.py migrate --noinput

#=============================================================================
# Step 9: Gunicorn systemd service
#=============================================================================
echo "[9/11] Setting up Gunicorn systemd service..."
cp "${PROJECT_DIR}/deploy/nihar-website.service" /etc/systemd/system/gunicorn-nihar.service
systemctl daemon-reload
systemctl enable gunicorn-nihar
systemctl restart gunicorn-nihar

sleep 2
if systemctl is-active --quiet gunicorn-nihar; then
    echo "  Gunicorn is running"
else
    echo "  WARNING: Gunicorn failed to start. Check: journalctl -u gunicorn-nihar -e"
fi

#=============================================================================
# Step 10: Nginx + SSL
#=============================================================================
echo "[10/11] Configuring Nginx..."
rm -f /etc/nginx/sites-enabled/default
mkdir -p /var/www/certbot

# Temporary HTTP-only config for certbot
cat > /etc/nginx/sites-available/nihargupte.com <<'NGINX_TEMP'
server {
    listen 80;
    server_name nihargupte.com www.nihargupte.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location /static/ {
        alias /home/deploy/nihar-website/staticfiles/;
    }

    location / {
        proxy_pass http://unix:/run/gunicorn/nihar-website.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}
NGINX_TEMP

ln -sf /etc/nginx/sites-available/nihargupte.com /etc/nginx/sites-enabled/nihargupte.com
nginx -t && systemctl reload nginx

echo "  Obtaining SSL certificate..."
certbot --nginx \
    -d "${DOMAIN}" -d "www.${DOMAIN}" \
    --non-interactive --agree-tos \
    --email "${CERTBOT_EMAIL}" \
    --redirect

# Install full production config with SSL
cp "${PROJECT_DIR}/deploy/nginx.conf" /etc/nginx/sites-available/nihargupte.com
nginx -t && systemctl reload nginx

#=============================================================================
# Step 11: Firewall
#=============================================================================
echo "[11/11] Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo ""
echo "=========================================="
echo "  Provisioning complete!"
echo "  Site live at: https://${DOMAIN}"
echo "=========================================="
echo ""
echo "Useful commands:"
echo "  sudo journalctl -u gunicorn-nihar -f          # Gunicorn logs"
echo "  sudo systemctl restart gunicorn-nihar          # Restart app"
echo "  sudo nginx -t && sudo systemctl reload nginx   # Reload Nginx"
echo "  sudo certbot renew --dry-run                   # Test cert renewal"
echo ""
echo "To deploy future updates, SSH as deploy:"
echo "  ssh deploy@204.168.208.228"
echo "  bash ~/nihar-website/deploy/update.sh"
