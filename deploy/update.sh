#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/deploy/nihar-website"
MAMBA_ROOT="/home/deploy/micromamba"
ENV_PYTHON="${MAMBA_ROOT}/envs/nihar-website/bin/python"

cd "${PROJECT_DIR}"

echo "Pulling latest changes..."
git pull
git lfs pull

# Only update conda env if environment.yml changed in this pull
if git diff HEAD@{1} --name-only 2>/dev/null | grep -q "environment.yml"; then
    echo "Updating conda environment..."
    "${MAMBA_ROOT}/bin/micromamba" update -y \
        -r "${MAMBA_ROOT}" \
        -n nihar-website \
        -f environment.yml
else
    echo "environment.yml unchanged, skipping conda update"
fi

echo "Collecting static files..."
"${ENV_PYTHON}" manage.py collectstatic --clear --noinput

echo "Fixing permissions..."
chmod -R o+rX "${PROJECT_DIR}/staticfiles"

echo "Running migrations..."
"${ENV_PYTHON}" manage.py migrate --noinput

echo "Restarting Gunicorn..."
sudo /bin/systemctl restart gunicorn-nihar

echo "Deployment complete!"
