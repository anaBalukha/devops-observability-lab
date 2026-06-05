# DevOps Observability Lab

## Objective

This project implements a complete observability system for a containerized application.

The system includes:

* A small Flask application
* Prometheus for metrics collection
* Grafana for metrics visualization and alerting
* Loki for log storage
* Promtail for log collection
* Docker Compose for one-command deployment
* 
## Chosen Stack

For this lab, I used the following stack:

| Requirement             | Tool Used                                           |
| ----------------------- | --------------------------------------------------- |
| Container orchestration | Docker Compose                                      |
| Application             | Python Flask                                        |
| Metrics collection      | Prometheus                                          |
| Metrics visualization   | Grafana                                             |
| Logging system          | Loki                                                |
| Log collector           | Promtail                                            |
| Alerting                | Prometheus alert rule displayed in Grafana Alerting |

I chose Loki + Promtail instead of the ELK Stack because it is lighter and easier to run locally with Docker Compose. It also integrates directly with Grafana, which makes it suitable for this lab.

## Architecture Diagram

mermaid
flowchart LR
User[User / Browser / curl] --> App[Flask Application Container]

    App -->|/metrics endpoint| Prometheus[Prometheus]
    Prometheus -->|PromQL queries| Grafana[Grafana Dashboard]
    Prometheus -->|Alert rule: error rate > 5/min| GrafanaAlert[Grafana Alerting]

    App -->|JSON log file| Promtail[Promtail]
    Promtail -->|Push logs| Loki[Loki]
    Loki -->|LogQL queries| GrafanaLogs[Grafana Explore Logs]

### Architecture Explanation

The application exposes metrics through the /metrics endpoint. Prometheus scrapes this endpoint every 5 seconds and stores the values as time-series metrics. Grafana uses Prometheus as a data source to display the custom metrics on a dashboard.

For logging, the application writes JSON logs to /var/log/app/app.log. This path is shared with Promtail through a Docker volume. Promtail reads the log file, extracts labels from the JSON fields, and pushes the logs to Loki. Grafana then uses Loki as a data source to search and filter logs.

The alert rule is configured in Prometheus using the expression increase(app_errors_total[1m]) > 5. Grafana displays this Prometheus-managed rule in the Alerting tab.

## Implementation Details

### Application

The application is written in Python using Flask.

It exposes the following endpoints:

| Endpoint                    | Purpose                           |
| --------------------------- | --------------------------------- |
| /                         | Shows basic app information       |
| /health                   | Health check endpoint             |
| /metrics                  | Prometheus metrics endpoint       |
| /error                    | Simulates one application error   |
| /generate-errors?count=10 | Simulates multiple errors quickly |

### Metrics Strategy

The application exposes custom Prometheus counters:

* app_requests_total
* app_errors_total

Prometheus scrapes the /metrics endpoint every 5 seconds.

The critical alert condition is:

promql
increase(app_errors_total[1m]) > 5

This means the alert fires if the application generates more than 5 errors during the last minute.

### Logging Strategy

The application writes logs in JSON format to:

`/var/log/app/app.log`

This directory is mounted to the host machine through Docker Compose.

Promtail reads the JSON log file, extracts fields such as level, 
path, method, status, and event, then sends the logs to Loki.
Grafana uses Loki as a data source for log search and filtering.
The application logs include fields such as timestamp, level, message, 
method, path, status, duration_ms, client_ip, request_id, and event. 
These fields make it possible to filter logs by specific values, for example 
only error logs.
Example Loki query for error logs:

`{service="observability-app", level="ERROR"}`

## How to Run the Project

### 1. Start all services

docker compose up --build

The whole observability system is started with this one command.

### 2. Open the services

| Service    | URL                   |
| ---------- | --------------------- |
| Flask app  | http://localhost:5000 |
| Prometheus | http://localhost:9090 |
| Grafana    | http://localhost:3000 |
| Loki       | http://localhost:3100 |

Grafana login:
```
username: admin
password: admin (changed it)
```

## How to Trigger the CRITICAL Alert

The alert rule checks whether the number of application errors increases by more than 5 during the last minute.

The Prometheus rule is:

`increase(app_errors_total[1m]) > 5`

To trigger the alert, run this command:

`curl.exe "http://localhost:5000/generate-errors?count=20"`

This endpoint simulates multiple application errors and increases the app_errors_total counter.

After running the command, wait around 10-20 seconds and open Grafana:
`http://localhost:3000`

Then go to: Alerting → Alert rules

The alert CriticalApplicationErrorRate should become Firing.

In my implementation, the alert appears in Grafana under *Data source-managed* because the alert rule is defined in Prometheus in this file:

`prometheus/alert.rules.yml`

## Log Queries

In Grafana:

1. Open *Explore*
2. Select *Loki*
3. Run this query:

```logql
{service="observability-app"}
```
To filter only error logs:
```logql
{service="observability-app", level="ERROR"}
```
To filter logs from the error simulation endpoint:
```logql
{service="observability-app", event="bulk_simulated_error"}
```

## Project Structure

```text
devops-observability-lab/
├── app/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── grafana/
│   ├── dashboards/
│   │   └── app-dashboard.json
│   └── provisioning/
│       ├── dashboards/
│       │   └── dashboard-provider.yml
│       └── datasources/
│           └── datasources.yml
├── loki/
│   └── loki-config.yml
├── prometheus/
│   ├── alert.rules.yml
│   └── prometheus.yml
├── promtail/
│   └── promtail-config.yml
├── screenshots/
│   ├── grafana-alert-rule.png
│   ├── grafana-dashboard.png
│   └── grafana-loki-logs.png
├── docker-compose.yml
└── README.md
```

## Evidence / Screenshots

### 1. Grafana dashboard displaying custom application metrics

![Grafana Metrics Dashboard](screenshots/grafana-dashboard.png)

### 2. Log analysis interface showing filtered JSON logs

![Grafana Loki Logs](screenshots/grafana-loki-logs.png)

### 3. Grafana Alerting tab showing active alert rule

![Grafana Alert Rule](screenshots/grafana-alert-rule.png)

## Analysis

### Why is JSON-structured logging more efficient than plain text logs?

JSON-structured logging is more efficient because each log entry has a predictable key-value format. Tools such as Promtail, Loki, Logstash, and Elasticsearch can easily parse fields like level, status, path, request_id, and timestamp.

With plain text logs, the system usually needs regular expressions or manual parsing. This is slower, less reliable, and harder to search. JSON logs make filtering easier, for example searching only logs where level="ERROR" or status=500.

### What is the fundamental technical difference between Prometheus and Loki?

Prometheus is a metrics system. It collects numeric time-series data, such as request counts, error counts, CPU usage, and latency. Prometheus is best for dashboards, alerting, and detecting trends over time.

Loki is a logging system. It stores event records produced by applications. Logs are usually text or JSON events that explain what happened inside the application.

The main difference is:

* Prometheus stores numeric metrics.
* Loki stores log events.

Metrics are better for fast alerting and system health overview. Logs are better for debugging and understanding the exact reason behind a problem.

### How would you handle long-term log retention for 6 months without depleting disk resources?

For long-term retention, I would avoid storing all logs forever on the local server disk.

A better approach would be:

1. Store recent logs locally for fast access, for example 7-14 days.
2. Move older logs to cheaper object storage such as Amazon S3, Azure Blob Storage, Google Cloud Storage, or MinIO.
3. Use retention policies to automatically delete logs after 6 months.
4. Reduce storage usage by compressing logs.
5. Keep only important logs for long periods, such as ERROR, WARN, audit logs, and security-related logs.
6. Avoid high-cardinality labels in Loki because they increase index size and storage cost.

This keeps the system useful for debugging and auditing without filling the disk.