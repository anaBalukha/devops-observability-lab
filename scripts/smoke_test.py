import json
import sys
import time
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

MAX_ATTEMPTS = 30
RETRY_DELAY_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 3


def application_is_ready(body: str) -> bool:
    data = json.loads(body)
    return data.get("status") == "UP"


def prometheus_is_ready(body: str) -> bool:
    return "ready" in body.lower()


def loki_is_ready(body: str) -> bool:
    return "ready" in body.lower()


def grafana_is_ready(body: str) -> bool:
    data = json.loads(body)
    return data.get("database") == "ok"


CHECKS: list[tuple[str, str, Callable[[str], bool]]] = [
    (
        "Application",
        "http://localhost:5000/health",
        application_is_ready,
    ),
    (
        "Prometheus",
        "http://localhost:9090/-/ready",
        prometheus_is_ready,
    ),
    (
        "Loki",
        "http://localhost:3100/ready",
        loki_is_ready,
    ),
    (
        "Grafana",
        "http://localhost:3000/api/health",
        grafana_is_ready,
    ),
]


def wait_for_service(
    name: str,
    url: str,
    validator: Callable[[str], bool],
) -> bool:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urlopen(
                url,
                timeout=REQUEST_TIMEOUT_SECONDS,
            ) as response:
                body = response.read().decode("utf-8")

                if response.status == 200 and validator(body):
                    print(f"[PASS] {name}: {url}")
                    return True

        except (
            HTTPError,
            URLError,
            TimeoutError,
            json.JSONDecodeError,
        ):
            pass

        print(
            f"[WAIT] {name}: attempt "
            f"{attempt}/{MAX_ATTEMPTS}"
        )
        time.sleep(RETRY_DELAY_SECONDS)

    print(f"[FAIL] {name}: {url}")
    return False


def main() -> int:
    print("Running post-deployment smoke tests...")

    results = [
        wait_for_service(name, url, validator)
        for name, url, validator in CHECKS
    ]

    if all(results):
        print("All smoke tests passed.")
        return 0

    print("One or more smoke tests failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())