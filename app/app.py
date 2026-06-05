import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

from flask import Flask, Response, g, jsonify, request
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

REQUEST_COUNTER = Counter(
    "app_requests_total",
    "Total number of HTTP requests received by the application",
    ["endpoint", "method", "status"]
)

ERROR_COUNTER = Counter(
    "app_errors_total",
    "Total number of application errors"
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
    logger = logging.getLogger("observability_app")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = JsonFormatter()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    log_dir = "/var/log/app"
    os.makedirs(log_dir, exist_ok=True)

    file_handler = logging.FileHandler(f"{log_dir}/app.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()


@app.before_request
def before_request():
    g.start_time = time.time()
    g.request_id = str(uuid.uuid4())


@app.after_request
def after_request(response):
    duration_ms = round((time.time() - g.start_time) * 1000, 2)

    endpoint = request.path
    method = request.method
    status = str(response.status_code)

    REQUEST_COUNTER.labels(
        endpoint=endpoint,
        method=method,
        status=status
    ).inc()

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
        }
    )

    return response


@app.route("/")
def home():
    return jsonify({
        "message": "DevOps Observability Lab application is running",
        "available_endpoints": [
            "/",
            "/health",
            "/metrics",
            "/error",
            "/generate-errors?count=10"
        ]
    })


@app.route("/health")
def health():
    return jsonify({"status": "UP"})


@app.route("/error")
def error():
    logger.error(
        "simulated_error_endpoint_called",
        extra={
            "request_id": getattr(g, "request_id", "unknown"),
            "method": request.method,
            "path": request.path,
            "status": 500,
            "event": "simulated_error",
        }
    )
    return jsonify({"error": "Simulated application error"}), 500


@app.route("/generate-errors")
def generate_errors():
    count = int(request.args.get("count", "10"))

    for i in range(count):
        ERROR_COUNTER.inc()
        logger.error(
            "bulk_simulated_error",
            extra={
                "request_id": getattr(g, "request_id", "unknown"),
                "method": request.method,
                "path": request.path,
                "status": 500,
                "event": "bulk_simulated_error",
            }
        )

    return jsonify({
        "message": f"Generated {count} simulated errors",
        "alert_condition": "Prometheus alert fires when app_errors_total increases by more than 5 in 1 minute"
    })


@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


