# Blue-Green Rollback Guide

## Overview

The project uses a blue-green deployment strategy behind an Nginx
gateway.

Two application services are available:

text
app-blue
app-green

Only one application color receives public traffic at a time.

The public endpoint is:

text
http://localhost:5000

Deployment state is stored locally in:

text
.deployment/active_color
.deployment/previous_color

These runtime state files are ignored by Git.

The runtime Nginx configuration is:

text
nginx/active.conf

This file is also ignored by Git because it changes whenever traffic is
switched.

## Normal Deployment Procedure

Deploy the next version using:

bash scripts/deploy.sh <version>

Example:

bash scripts/deploy.sh 1.1.0

The deployment script:

1. Reads the active color.
2. Selects the inactive color.
3. Builds and recreates the inactive application container.
4. Waits for the container to become healthy.
5. Verifies the backend color.
6. Verifies the backend version.
7. Generates the Nginx configuration.
8. Validates Nginx using nginx -t.
9. Reloads Nginx.
10. Verifies the public application.
11. Updates deployment-state files.

If public verification fails, traffic is automatically restored to the
original active color.

## Normal Rollback Procedure

Run:

bash scripts/rollback.sh

The rollback script:

1. Reads the current active color.
2. Reads the previous stable color.
3. Confirms the previous color is different.
4. Verifies the previous backend.
5. Generates the Nginx configuration.
6. Validates Nginx using nginx -t.
7. Reloads Nginx.
8. Verifies the public health endpoint.
9. Updates deployment-state files.

A successful rollback displays output similar to:

text
Rollback completed successfully.
Active color: blue
Previous color: green

The exact colors depend on which environment was previously active.

## Verify the Rollback

Check public traffic:

curl -s http://localhost:5000/health

Check active deployment state:

cat .deployment/active_color

Check previous deployment state:

cat .deployment/previous_color

Run all smoke tests:

python scripts/smoke_test.py

Check all containers:

docker compose ps

## Check Both Backends

Check blue:

docker exec observability-gateway \
  wget -qO- http://app-blue:5000/health

Check green:

docker exec observability-gateway \
  wget -qO- http://app-green:5000/health

The health responses include:

- status
- color
- version

Example:

{
  "color": "blue",
  "status": "UP",
  "version": "1.0.0"
}

## Manual Emergency Rollback

Use this procedure only when scripts/rollback.sh cannot run.

### 1. Identify the stable backend

Check blue:

docker exec observability-gateway \
  wget -qO- http://app-blue:5000/health

Check green:

docker exec observability-gateway \
  wget -qO- http://app-green:5000/health

Choose the backend that is healthy and contains the stable application
version.

### 2. Update the runtime gateway configuration

Edit:

text
nginx/active.conf

For blue:

nginx
upstream active_backend {
    server app-blue:5000;
    keepalive 16;
}

server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://active_backend;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

For green, replace:

text
app-blue

with:

text
app-green

### 3. Validate Nginx

Run:

docker exec observability-gateway nginx -t

Do not reload Nginx if validation fails.

### 4. Reload Nginx

Run:

docker exec observability-gateway nginx -s reload

### 5. Verify public traffic

Run:

curl -s http://localhost:5000/health

Confirm the expected color, status, and version.

### 6. Correct deployment state

Example when blue becomes active:

printf "blue\n" > .deployment/active_color
printf "green\n" > .deployment/previous_color

Example when green becomes active:

printf "green\n" > .deployment/active_color
printf "blue\n" > .deployment/previous_color

### 7. Run smoke tests

Run:

python scripts/smoke_test.py

## Failed Deployment Protection

Before switching traffic, scripts/deploy.sh verifies:

- Target container health
- Target application color
- Target application version

After switching traffic, it verifies:

- Public health status
- Public application color
- Public application version

If public deployment verification fails, the script:

1. Regenerates the gateway configuration for the original color.
2. Validates Nginx.
3. Reloads Nginx.
4. Verifies that public traffic was restored.
5. Exits with an error.

## CI Deployment Verification

GitHub Actions automatically tests the complete deployment process.

The workflow verifies:

- Initial blue environment
- Deployment to green
- Green application version
- Green application health
- Rollback to blue
- Blue application health
- Complete smoke-test success

The workflow job is named:

text
Blue-Green Deployment Verification

## Rollback Safety Rules

Do not delete the previously active application container immediately
after deployment. It is required for fast rollback.

Do not use:

docker compose down -v

during normal rollback because it deletes persistent volumes.

Do not reload Nginx unless:

docker exec observability-gateway nginx -t

succeeds.

Always run:

python scripts/smoke_test.py

after rollback.

Do not manually edit:

text
.deployment/active_color
.deployment/previous_color

unless performing the documented emergency rollback procedure.

## Rollback Completion Checklist

A rollback is complete when:

- The previous backend is healthy.
- Nginx validation succeeds.
- Nginx reload succeeds.
- The public endpoint reports the expected color.
- The public endpoint reports "status": "UP".
- The deployment state contains the expected active color.
- All smoke tests pass.
- Monitoring and logging services remain available.
