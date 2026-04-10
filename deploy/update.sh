#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/deploy/nihar-website"
MAMBA_ROOT="/home/deploy/micromamba"
ENV_PYTHON="${MAMBA_ROOT}/envs/nihar-website/bin/python"

cd "${PROJECT_DIR}"

echo "Pulling latest changes..."
git pull
git lfs pull

echo "Updating conda environment..."
"${MAMBA_ROOT}/bin/micromamba" update -y \
    -r "${MAMBA_ROOT}" \
    -n nihar-website \
    -f environment.yml

echo "Collecting static files..."
"${ENV_PYTHON}" manage.py collectstatic --noinput

echo "Running migrations..."
"${ENV_PYTHON}" manage.py migrate --noinput

echo "Restarting Gunicorn..."
sudo /bin/systemctl restart gunicorn-nihar

echo "Deployment complete!"
