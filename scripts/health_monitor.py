import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

CHECK_INTERVAL_SECONDS = int(
    os.getenv("CHECK_INTERVAL_SECONDS", "10")
)

REQUEST_TIMEOUT_SECONDS = float(
    os.getenv("REQUEST_TIMEOUT_SECONDS", "3")
)

HEALTH_LOG_FILE = Path(
    os.getenv(
        "HEALTH_LOG_FILE",
        "logs/health/health.log",
    )
)

SERVICES = {
    "application": os.getenv(
        "APP_HEALTH_URL",
        "http://localhost:5000/health",
    ),
    "prometheus": os.getenv(
        "PROMETHEUS_HEALTH_URL",
        "http://localhost:9090/-/ready",
    ),
    "loki": os.getenv(
        "LOKI_HEALTH_URL",
        "http://localhost:3100/ready",
    ),
    "grafana": os.getenv(
        "GRAFANA_HEALTH_URL",
        "http://localhost:3000/api/health",
    ),
}


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_service(
    service_name: str,
    url: str,
) -> dict[str, object]:
    started_at = perf_counter()

    try:
        with urlopen(
            url,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            response.read()

            http_status = response.status

            status = (
                "UP"
                if 200 <= http_status < 300
                else "DOWN"
            )

            error_message = None

    except HTTPError as error:
        http_status = error.code
        status = "DOWN"
        error_message = str(error)

    except (
        URLError,
        TimeoutError,
        OSError,
    ) as error:
        http_status = None
        status = "DOWN"
        error_message = str(error)

    response_time_ms = round(
        (perf_counter() - started_at) * 1000,
        2,
    )

    return {
        "timestamp": current_timestamp(),
        "service": service_name,
        "url": url,
        "status": status,
        "http_status": http_status,
        "response_time_ms": response_time_ms,
        "error": error_message,
    }


def write_log_entry(entry: dict[str, object]) -> None:
    HEALTH_LOG_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_line = json.dumps(entry)

    print(log_line, flush=True)

    with HEALTH_LOG_FILE.open(
        "a",
        encoding="utf-8",
    ) as log_file:
        log_file.write(f"{log_line}\n")


def run_health_checks() -> None:
    for service_name, url in SERVICES.items():
        result = check_service(
            service_name,
            url,
        )

        write_log_entry(result)


def main() -> None:
    print(
        "Continuous health monitoring started.",
        flush=True,
    )

    while True:
        run_health_checks()
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()