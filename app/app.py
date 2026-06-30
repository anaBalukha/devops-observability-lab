import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

from flask import Flask, Response, g, jsonify, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

app = Flask(__name__)

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
APP_COLOR = os.getenv("APP_COLOR", "blue")
MAX_GENERATED_ERRORS = 100

DEFAULT_LOG_DIR = (
    "/var/log/app"
    if os.path.exists("/.dockerenv")
    else "logs/app"
)

LOG_DIR = os.getenv("LOG_DIR", DEFAULT_LOG_DIR)

REQUEST_COUNTER = Counter(
    "app_requests_total",
    "Total number of HTTP requests received by the application",
    ["endpoint", "method", "status"],
)

ERROR_COUNTER = Counter(
    "app_errors_total",
    "Total number of application errors",
)

REQUEST_DURATION = Histogram(
    "app_request_duration_seconds",
    "HTTP request duration in seconds",
    ["endpoint", "method"],
)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        extra_fields = [
            "request_id",
            "method",
            "path",
            "status",
            "duration_ms",
            "client_ip",
            "event",
        ]

        for field in extra_fields:
            if hasattr(record, field):
                log_record[field] = getattr(record, field)

        return json.dumps(log_record)


def setup_logger():
    application_logger = logging.getLogger(
        "observability_app"
    )

    application_logger.setLevel(logging.INFO)
    application_logger.handlers.clear()

    formatter = JsonFormatter()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    application_logger.addHandler(stream_handler)

    os.makedirs(LOG_DIR, exist_ok=True)

    file_handler = logging.FileHandler(
        os.path.join(LOG_DIR, "app.log")
    )
    file_handler.setFormatter(formatter)
    application_logger.addHandler(file_handler)

    return application_logger


logger = setup_logger()


@app.before_request
def before_request():
    g.start_time = time.perf_counter()
    g.request_id = str(uuid.uuid4())


@app.after_request
def after_request(response):
    duration_seconds = time.perf_counter() - g.start_time
    duration_ms = round(duration_seconds * 1000, 2)

    endpoint = request.path
    method = request.method
    status = str(response.status_code)

    REQUEST_COUNTER.labels(
        endpoint=endpoint,
        method=method,
        status=status,
    ).inc()

    REQUEST_DURATION.labels(
        endpoint=endpoint,
        method=method,
    ).observe(duration_seconds)

    if response.status_code >= 500:
        ERROR_COUNTER.inc()

    logger.info(
        "request_completed",
        extra={
            "request_id": g.request_id,
            "method": method,
            "path": endpoint,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": request.remote_addr,
            "event": "http_request",
        },
    )

    return response


@app.route("/")
def home():
    return jsonify(
        {
            "message": (
                "DevOps Observability Lab "
                "application is running"
            ),
            "version": APP_VERSION,
            "color": APP_COLOR,
            "available_endpoints": [
                "/",
                "/health",
                "/metrics",
                "/greet?name=Anna",
                "/error",
                "/generate-errors?count=10",
            ],
        }
    )


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "UP",
            "version": APP_VERSION,
            "color": APP_COLOR,
        }
    )


@app.route("/greet")
def greet():
    name = request.args.get("name", "").strip()

    if not name:
        return jsonify({"error": "name is required"}), 400

    if len(name) > 50:
        return (
            jsonify(
                {
                    "error": (
                        "name must be 50 characters or fewer"
                    )
                }
            ),
            400,
        )

    return jsonify({"message": f"Hello, {name}"})


@app.route("/error")
def error():
    logger.error(
        "simulated_error_endpoint_called",
        extra={
            "request_id": getattr(
                g,
                "request_id",
                "unknown",
            ),
            "method": request.method,
            "path": request.path,
            "status": 500,
            "event": "simulated_error",
        },
    )

    return (
        jsonify(
            {
                "error": "Simulated application error"
            }
        ),
        500,
    )


@app.route("/generate-errors")
def generate_errors():
    raw_count = request.args.get("count", "10")

    try:
        count = int(raw_count)
    except ValueError:
        return (
            jsonify(
                {
                    "error": "count must be an integer"
                }
            ),
            400,
        )

    if count < 1 or count > MAX_GENERATED_ERRORS:
        return (
            jsonify(
                {
                    "error": (
                        "count must be between "
                        f"1 and {MAX_GENERATED_ERRORS}"
                    )
                }
            ),
            400,
        )

    for _ in range(count):
        ERROR_COUNTER.inc()

        logger.error(
            "bulk_simulated_error",
            extra={
                "request_id": getattr(
                    g,
                    "request_id",
                    "unknown",
                ),
                "method": request.method,
                "path": request.path,
                "status": 500,
                "event": "bulk_simulated_error",
            },
        )

    return jsonify(
        {
            "message": (
                f"Generated {count} simulated errors"
            ),
            "alert_condition": (
                "Prometheus alert fires when "
                "app_errors_total increases by "
                "more than 5 in 1 minute"
            ),
        }
    )


@app.route("/metrics")
def metrics():
    return Response(
        generate_latest(),
        content_type=CONTENT_TYPE_LATEST,
    )


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
    )