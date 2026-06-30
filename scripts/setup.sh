#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Checking required tools..."

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: Docker is not installed."
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "ERROR: Docker Compose is unavailable."
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "ERROR: Docker Desktop is not running."
    exit 1
fi

if command -v python >/dev/null 2>&1; then
    PYTHON_COMMAND="python"
elif command -v py >/dev/null 2>&1; then
    PYTHON_COMMAND="py"
else
    echo "ERROR: Python is not installed."
    exit 1
fi

if [[ ! -f ".env" ]]; then
    echo "Creating local .env configuration..."

    GRAFANA_PASSWORD="$(
        "$PYTHON_COMMAND" -c \
        "import secrets; print(secrets.token_urlsafe(24))"
    )"

    cat > .env <<EOF
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
APP_VERSION=1.0.0
APP_COLOR=blue
EOF

    echo "Created .env with a generated Grafana password."
else
    echo "Using the existing local .env file."
fi

if [[ ! -f "nginx/active.conf" ]]; then
    echo "Creating initial blue gateway configuration..."
    cp nginx/default.conf nginx/active.conf
fi

echo "Validating Docker Compose configuration..."
docker compose config --quiet

echo "Building and starting all services..."
docker compose up -d --build

echo "Running deployment verification..."
"$PYTHON_COMMAND" scripts/smoke_test.py

echo
echo "Environment preparation completed successfully."
echo "Application: http://localhost:5000"
echo "Grafana:    http://localhost:3000"
echo "Prometheus: http://localhost:9090"
echo "Loki:       http://localhost:3100"
echo
echo "Grafana credentials are stored in the local .env file."
