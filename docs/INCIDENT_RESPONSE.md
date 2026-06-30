# Incident Response Guide

## Purpose

This guide explains how to detect, investigate, contain, recover from,
verify, and document an incident affecting the DevOps Observability Lab.

## Incident Examples

An incident may include:

- The public application health endpoint is unavailable.
- The Nginx gateway is unavailable.
- Application errors exceed five errors per minute.
- Prometheus cannot scrape metrics.
- Loki or Promtail stops collecting logs.
- Grafana becomes unavailable.
- A blue-green deployment fails.
- A container repeatedly restarts.
- Smoke tests fail after deployment.
- A dependency vulnerability is discovered.
- A secret is detected in the repository.
- A container image contains a critical vulnerability.

## Incident Severity Levels

### Critical

Examples:

- Public application unavailable
- Both blue and green environments unavailable
- Exposed secret or credential
- Critical container vulnerability
- Monitoring stack completely unavailable

Required action:

text
Immediate investigation and recovery

### High

Examples:

- New deployment unhealthy
- Error-rate alert active
- Prometheus unable to scrape the application
- Repeated application container restarts

Required action:

text
Investigate as soon as possible

### Medium

Examples:

- One monitoring component unavailable
- Delayed log collection
- Performance objective exceeded
- Health monitor reports intermittent failures

Required action:

text
Investigate and schedule remediation

## 1. Detect the Incident

Check all services:

docker compose ps

Check the public application:

curl -i http://localhost:5000/health

Run the complete smoke test:

python scripts/smoke_test.py

Inspect the health-monitor logs:

docker compose logs --tail=50 health-monitor

Inspect persistent health records:

tail -n 50 logs/health/health.log

Open the monitoring interfaces:

text
Grafana:    http://localhost:3000
Prometheus: http://localhost:9090
Loki:       http://localhost:3100

## 2. Determine the Impact

Identify:

- Which service is unavailable?
- When did the failure begin?
- Are all requests failing or only one endpoint?
- Is the active environment blue or green?
- Which application version is active?
- Did the incident begin after a deployment?
- Are metrics still available?
- Are logs still being collected?
- Are containers restarting automatically?
- Are GitHub Actions checks green for the deployed commit?

Check the active deployment:

cat .deployment/active_color

Check the previous deployment:

cat .deployment/previous_color

Check the active public version and color:

curl -s http://localhost:5000/health

Check blue directly:

docker exec observability-gateway \
  wget -qO- http://app-blue:5000/health

Check green directly:

docker exec observability-gateway \
  wget -qO- http://app-green:5000/health

## 3. Inspect Logs

Application blue logs:

docker compose logs --tail=100 app-blue

Application green logs:

docker compose logs --tail=100 app-green

Gateway logs:

docker compose logs --tail=100 gateway

Prometheus logs:

docker compose logs --tail=100 prometheus

Loki logs:

docker compose logs --tail=100 loki

Promtail logs:

docker compose logs --tail=100 promtail

Grafana logs:

docker compose logs --tail=100 grafana

Health-monitor logs:

docker compose logs --tail=100 health-monitor

All service logs:

docker compose logs --tail=100

## 4. Check Metrics and Alerts

Useful Prometheus metrics:

text
app_requests_total
app_errors_total
app_request_duration_seconds

Check whether the application target is up:

promql
up

Check recent application errors:

promql
increase(app_errors_total[1m])

Check request rate:

promql
rate(app_requests_total[5m])

Check the 95th percentile request duration:

promql
histogram_quantile(
  0.95,
  sum(rate(app_request_duration_seconds_bucket[5m])) by (le)
)

## 5. Contain the Incident

If the incident began after a deployment, immediately run:

bash scripts/rollback.sh

The rollback script:

1. Reads the active and previous deployment colors.
2. Verifies the previous backend.
3. Generates the Nginx configuration.
4. Validates Nginx using nginx -t.
5. Reloads Nginx.
6. Verifies the public application response.
7. Updates deployment-state files.

If a container stopped unexpectedly, Docker may restart it automatically
because the services use:

restart: unless-stopped

Check the restart count:

docker inspect \
  --format='RestartCount={{.RestartCount}} Status={{.State.Status}}' \
  observability-app-blue

Replace the container name with the affected container when necessary.

## 6. Recover the Service

After rollback or automatic restart, verify:

curl -s http://localhost:5000/health

Run smoke tests:

python scripts/smoke_test.py

Check all services:

docker compose ps

If a single service must be recreated:

docker compose up -d --force-recreate <service-name>

Example:

docker compose up -d --force-recreate gateway

If the environment cannot be repaired, recreate it:

docker compose down --remove-orphans
bash scripts/setup.sh

Do not use:

docker compose down -v

unless deleting all persistent monitoring data is intentional.

## 7. Verify Recovery

Recovery is complete only when:

- The gateway is healthy.
- The public health endpoint returns HTTP 200.
- The health response contains "status": "UP".
- The expected application color is active.
- Prometheus reports ready.
- Loki reports ready.
- Grafana reports a healthy database.
- Health-monitor entries report "status": "UP".
- Smoke tests report All smoke tests passed.
- GitHub Actions checks are green.

## 8. Security Incident Procedure

If a secret is detected:

1. Remove the secret from the code.
2. Revoke or rotate the exposed credential.
3. Confirm .env is ignored by Git.
4. Run the secrets-scanning workflow.
5. Review repository history for exposure.
6. Document the affected credential and response.

If a vulnerability is detected:

1. Identify the affected dependency or image.
2. Upgrade to the fixed version.
3. Run:

pip-audit -r app/requirements.txt

4. Run:

bandit -r app -ll

5. Run the Advanced Security Scans workflow.
6. Rebuild and verify the container image.
7. Document the vulnerability and remediation.

## 9. Document the Incident

Record:

- Incident title
- Start time
- Detection time
- Recovery time
- Affected service
- User-visible symptoms
- Active application color
- Active application version
- Relevant logs and metrics
- Root cause
- Containment action
- Recovery action
- Whether rollback was required
- Verification results
- Prevention improvements

## Incident Report Template

text
Incident title:

Start time:

Detection time:

Recovery time:

Affected services:

Public impact:

Active color and version:

Symptoms:

Root cause:

Containment action:

Recovery action:

Rollback performed:

Verification results:

Preventive improvements:

## Example Incident Record

```text
Incident title:
Public application unavailable after deployment

Detected:
Health monitor reported gateway DOWN

Impact:
Public /health endpoint unavailable

Root cause:
Green deployment failed post-deployment verification

Containment:
Deployment script restored traffic to blue

Recovery:
Blue backend verified and Nginx reloaded

Verification:
Public health endpoint returned UP
All smoke tests passed

Prevention:
Keep deployment verification and automatic traffic restoration enabled
