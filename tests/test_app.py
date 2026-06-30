import pytest

from app.app import app


@pytest.fixture()
def client():
    app.config.update(TESTING=True)

    with app.test_client() as test_client:
        yield test_client


def test_home_returns_application_information(client):
    response = client.get("/")

    assert response.status_code == 200

    data = response.get_json()

    assert (
        data["message"]
        == (
            "DevOps Observability Lab "
            "application is running"
        )
    )
    assert "version" in data
    assert "color" in data


def test_health_returns_up(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "UP"


def test_metrics_exposes_custom_metrics(client):
    response = client.get("/metrics")

    assert response.status_code == 200

    body = response.get_data(as_text=True)

    assert "app_requests_total" in body
    assert "app_errors_total" in body
    assert "app_request_duration_seconds" in body


def test_error_endpoint_returns_500(client):
    response = client.get("/error")

    assert response.status_code == 500
    assert (
        response.get_json()["error"]
        == "Simulated application error"
    )


def test_generate_errors_accepts_valid_count(client):
    response = client.get(
        "/generate-errors?count=6"
    )

    assert response.status_code == 200
    assert (
        response.get_json()["message"]
        == "Generated 6 simulated errors"
    )


def test_generate_errors_uses_default_count(client):
    response = client.get("/generate-errors")

    assert response.status_code == 200
    assert (
        response.get_json()["message"]
        == "Generated 10 simulated errors"
    )


def test_generate_errors_rejects_non_integer(client):
    response = client.get(
        "/generate-errors?count=bad"
    )

    assert response.status_code == 400
    assert (
        response.get_json()["error"]
        == "count must be an integer"
    )


@pytest.mark.parametrize(
    "count",
    [0, -1, 101],
)
def test_generate_errors_rejects_bad_range(
    client,
    count,
):
    response = client.get(
        f"/generate-errors?count={count}"
    )

    assert response.status_code == 400
    assert (
        response.get_json()["error"]
        == "count must be between 1 and 100"
    )


def test_greet_accepts_valid_name(client):
    response = client.get(
        "/greet?name=Anna"
    )

    assert response.status_code == 200
    assert (
        response.get_json()["message"]
        == "Hello, Anna"
    )


def test_greet_requires_name(client):
    response = client.get("/greet")

    assert response.status_code == 400
    assert (
        response.get_json()["error"]
        == "name is required"
    )


def test_greet_rejects_long_name(client):
    long_name = "a" * 51

    response = client.get(
        f"/greet?name={long_name}"
    )

    assert response.status_code == 400
    assert (
        response.get_json()["error"]
        == "name must be 50 characters or fewer"
    )