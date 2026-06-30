# Service-Level Objectives

## Purpose

This document defines the reliability objectives for the DevOps
Observability Lab application.

The project runs locally using Docker Compose. The objectives are
measured using Prometheus metrics, Grafana dashboards, Loki logs,
Docker health checks, the continuous health-monitor service, and
GitHub Actions.

## Availability Objective

Target availability:

text
99% availability over a rolling 30-day period

The public application is considered available when:

- The Nginx gateway responds to /health.
- The HTTP response status is 200.
- The JSON response contains "status": "UP".

The public health endpoint is:

text
http://localhost:5000/health

Prometheus scrapes the application through the Nginx gateway.

The continuous health-monitor service also checks the application every
10 seconds and writes structured JSON results to:

text
logs/health/health.log

## Response-Time Objective

Target:

text
95% of application requests should complete in less than 500 ms.

The application exposes this Prometheus histogram:

text
app_request_duration_seconds

This metric can be used to calculate response-time percentiles.

Example Prometheus query for the approximate 95th percentile:

promql
histogram_quantile(
  0.95,
  sum(rate(app_request_duration_seconds_bucket[5m])) by (le)
)

## Error-Rate Objective

Target:

text
The normal HTTP 5xx error ratio should remain below 1%.

The application exposes:

text
app_requests_total
app_errors_total

A critical Prometheus alert is triggered when application errors
increase by more than five during one minute.

## Recovery-Time Objective

Target recovery time:

text
Restore the public application within 10 minutes.

Recovery mechanisms include:

1. Docker automatic restart using:

restart: unless-stopped

2. Blue-green rollback using:

bash scripts/rollback.sh

3. Complete environment recreation using:

bash scripts/setup.sh

## Deployment Reliability Objective

Every deployment must satisfy all of these conditions:

- The inactive blue or green application container builds successfully.
- The inactive container becomes healthy.
- The health response reports the expected application color.
- The health response reports the expected application version.
- Nginx configuration validation succeeds.
- Public traffic returns the expected color and version.
- Post-deployment smoke tests succeed.
- The previous environment remains available for rollback.

The deployment command is:

bash scripts/deploy.sh <version>

Example:

bash scripts/deploy.sh 1.1.0

If public deployment verification fails, the deployment script restores
traffic to the previously active application color.

## Rollback Objective

Rollback must:

- Verify the previous backend before switching traffic.
- Validate the generated Nginx configuration.
- Reload Nginx without restarting the complete environment.
- Verify the public health endpoint.
- Update deployment-state files.
- Complete without deleting persistent monitoring data.

The rollback command is:

bash scripts/rollback.sh

## Monitoring Objective

The following services must remain observable:

- Application
- Nginx gateway
- Prometheus
- Grafana
- Loki
- Promtail
- Health monitor
- Blue application container
- Green application container

The monitoring stack must provide:

- Application request metrics
- Application error metrics
- Request-duration metrics
- Structured JSON logs
- Service health status
- Alerting for excessive application errors
- Persistent health-check records

## Security Objective

Every change pushed to main or dev must pass:

- Ruff linting
- Unit tests
- Minimum 80% test coverage
- Python dependency vulnerability scanning
- Bandit static-security analysis
- Secrets scanning
- Repository dependency scanning
- Docker and configuration scanning
- Container-image scanning
- Docker Compose validation
- Docker image build verification
- Blue-green deployment verification
- Rollback verification
- Post-deployment smoke testing

## Measurement Sources

Reliability is measured using:

- Prometheus metrics
- Grafana dashboards
- Loki logs
- Application JSON logs
- Docker health checks
- Continuous health-monitor JSON logs
- Nginx gateway health checks
- GitHub Actions workflow results
- Blue-green deployment state files

## Review Schedule

These objectives should be reviewed whenever:

- A new service is added.
- Deployment behavior changes.
- Alert thresholds change.
- A significant incident occurs.
- Monitoring or logging architecture changes.
