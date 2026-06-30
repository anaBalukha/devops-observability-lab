#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STATE_DIR=".deployment"
ACTIVE_FILE="${STATE_DIR}/active_color"
PREVIOUS_FILE="${STATE_DIR}/previous_color"
NGINX_CONFIG="nginx/active.conf"

VERSION="${1:-}"

if [[ -z "$VERSION" ]]; then
    echo "Usage: bash scripts/deploy.sh <version>"
    echo "Example: bash scripts/deploy.sh 1.1.0"
    exit 1
fi

mkdir -p "$STATE_DIR"

if [[ ! -f "$ACTIVE_FILE" ]]; then
    printf "blue\n" > "$ACTIVE_FILE"
fi

if [[ ! -f "$PREVIOUS_FILE" ]]; then
    printf "blue\n" > "$PREVIOUS_FILE"
fi

ACTIVE_COLOR="$(tr -d '\r\n' < "$ACTIVE_FILE")"

case "$ACTIVE_COLOR" in
    blue)
        TARGET_COLOR="green"
        ;;
    green)
        TARGET_COLOR="blue"
        ;;
    *)
        echo "ERROR: Invalid active color: ${ACTIVE_COLOR}"
        exit 1
        ;;
esac

TARGET_SERVICE="app-${TARGET_COLOR}"


json_value_matches() {
    local payload="$1"
    local field="$2"
    local expected="$3"

    python -c '
import json
import sys

field = sys.argv[1]
expected = sys.argv[2]
payload = sys.argv[3]

data = json.loads(payload)

if str(data.get(field)) == expected:
    sys.exit(0)

sys.exit(1)
' "$field" "$expected" "$payload" 2>/dev/null
}


write_gateway_config() {
    local color="$1"

    cat > "$NGINX_CONFIG" <<EOF
upstream active_backend {
    server app-${color}:5000;
    keepalive 16;
}

server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://active_backend;
        proxy_http_version 1.1;

        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

    echo "Validating Nginx configuration..."

    docker exec observability-gateway nginx -t

    echo "Reloading Nginx..."

    docker exec observability-gateway nginx -s reload
}


wait_for_container_health() {
    local service="$1"
    local container_id
    local status

    for attempt in $(seq 1 30); do
        container_id="$(docker compose ps -q "$service")"

        if [[ -n "$container_id" ]]; then
            status="$(
                docker inspect \
                    --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
                    "$container_id" \
                    2>/dev/null || true
            )"

            echo "Health check ${attempt}/30: ${status:-unknown}"

            if [[ "$status" == "healthy" ]]; then
                return 0
            fi

            if [[ "$status" == "unhealthy" ]]; then
                echo "ERROR: ${service} became unhealthy."

                docker compose logs \
                    --tail=50 \
                    "$service"

                return 1
            fi
        else
            echo "Health check ${attempt}/30: container not found"
        fi

        sleep 2
    done

    echo "ERROR: ${service} did not become healthy."

    docker compose logs \
        --tail=50 \
        "$service"

    return 1
}


verify_backend() {
    local color="$1"
    local version="$2"
    local response

    response="$(
        docker exec observability-gateway \
            wget -qO- \
            "http://app-${color}:5000/health"
    )"

    echo "Inactive backend response: ${response}"

    if ! json_value_matches "$response" "color" "$color"; then
        echo "ERROR: Backend color verification failed."
        return 1
    fi

    if ! json_value_matches "$response" "version" "$version"; then
        echo "ERROR: Backend version verification failed."
        return 1
    fi

    echo "Inactive backend verification passed."
}


verify_public_deployment() {
    local color="$1"
    local version="$2"
    local response

    for attempt in $(seq 1 20); do
        response="$(
            curl -fsS \
                http://localhost:5000/health \
                2>/dev/null || true
        )"

        if json_value_matches "$response" "color" "$color" \
            && json_value_matches "$response" "version" "$version"
        then
            echo "Public response: ${response}"
            return 0
        fi

        echo "Public verification ${attempt}/20..."
        sleep 1
    done

    echo "ERROR: Public deployment verification failed."
    return 1
}


verify_public_color() {
    local color="$1"
    local response

    for attempt in $(seq 1 20); do
        response="$(
            curl -fsS \
                http://localhost:5000/health \
                2>/dev/null || true
        )"

        if json_value_matches "$response" "color" "$color"; then
            echo "Restored public response: ${response}"
            return 0
        fi

        echo "Restore verification ${attempt}/20..."
        sleep 1
    done

    echo "ERROR: Could not verify restored traffic."
    return 1
}


echo "Current active color: ${ACTIVE_COLOR}"
echo "Deployment target: ${TARGET_COLOR}"
echo "Deploying version: ${VERSION}"
echo

APP_VERSION="$VERSION" \
    docker compose up \
        -d \
        --build \
        --no-deps \
        --force-recreate \
        "$TARGET_SERVICE"

wait_for_container_health "$TARGET_SERVICE"

verify_backend \
    "$TARGET_COLOR" \
    "$VERSION"

echo
echo "Switching public traffic to ${TARGET_COLOR}..."

write_gateway_config "$TARGET_COLOR"

if ! verify_public_deployment "$TARGET_COLOR" "$VERSION"; then
    echo
    echo "Deployment verification failed."
    echo "Automatically restoring traffic to ${ACTIVE_COLOR}..."

    write_gateway_config "$ACTIVE_COLOR"
    verify_public_color "$ACTIVE_COLOR" || true

    exit 1
fi

printf "%s\n" "$ACTIVE_COLOR" > "$PREVIOUS_FILE"
printf "%s\n" "$TARGET_COLOR" > "$ACTIVE_FILE"

echo
echo "Deployment completed successfully."
echo "Active color: ${TARGET_COLOR}"
echo "Previous color: ${ACTIVE_COLOR}"
echo "Version: ${VERSION}"