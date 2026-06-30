#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STATE_DIR=".deployment"
ACTIVE_FILE="${STATE_DIR}/active_color"
PREVIOUS_FILE="${STATE_DIR}/previous_color"
NGINX_CONFIG="nginx/active.conf"

if [[ ! -f "$ACTIVE_FILE" || ! -f "$PREVIOUS_FILE" ]]; then
    echo "ERROR: Deployment state does not exist."
    echo "Run a blue-green deployment first."
    exit 1
fi

ACTIVE_COLOR="$(tr -d '\r\n' < "$ACTIVE_FILE")"
ROLLBACK_COLOR="$(tr -d '\r\n' < "$PREVIOUS_FILE")"

if [[ "$ACTIVE_COLOR" == "$ROLLBACK_COLOR" ]]; then
    echo "ERROR: No different previous deployment is available."
    exit 1
fi

case "$ROLLBACK_COLOR" in
    blue|green)
        ;;
    *)
        echo "ERROR: Invalid rollback color: ${ROLLBACK_COLOR}"
        exit 1
        ;;
esac


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


verify_backend() {
    local color="$1"
    local response

    response="$(
        docker exec observability-gateway \
            wget -qO- \
            "http://app-${color}:5000/health"
    )"

    echo "Rollback backend response: ${response}"

    if ! json_value_matches "$response" "color" "$color"; then
        echo "ERROR: Rollback backend verification failed."
        return 1
    fi

    echo "Rollback backend verification passed."
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
            echo "Public response after rollback: ${response}"
            return 0
        fi

        echo "Rollback verification ${attempt}/20..."
        sleep 1
    done

    echo "ERROR: Rollback verification failed."
    return 1
}


echo "Current active color: ${ACTIVE_COLOR}"
echo "Rollback target: ${ROLLBACK_COLOR}"
echo

verify_backend "$ROLLBACK_COLOR"

echo
echo "Switching public traffic to ${ROLLBACK_COLOR}..."

write_gateway_config "$ROLLBACK_COLOR"
verify_public_color "$ROLLBACK_COLOR"

printf "%s\n" "$ACTIVE_COLOR" > "$PREVIOUS_FILE"
printf "%s\n" "$ROLLBACK_COLOR" > "$ACTIVE_FILE"

echo
echo "Rollback completed successfully."
echo "Active color: ${ROLLBACK_COLOR}"
echo "Previous color: ${ACTIVE_COLOR}"