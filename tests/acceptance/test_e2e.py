"""
End-to-end acceptance smoke tests for Gypsi Trading Agent.

Verifies that the containerized stack boots and responds properly over HTTP
against a fresh database.
"""
import os
import httpx
import pytest

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=API_BASE_URL, timeout=10.0) as client:
        yield client


def test_health_endpoint(client: httpx.Client):
    """GET /health must return 200 OK and {'status': 'ok'}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_trades_endpoint_returns_empty_list_on_fresh_db(client: httpx.Client):
    """GET /trades must return 200 OK and an empty list on a fresh database."""
    response = client.get("/trades")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data == []


def test_round_table_recent_endpoint_returns_empty_list_on_fresh_db(client: httpx.Client):
    """GET /round-table/recent must return 200 OK and an empty list on a fresh database."""
    response = client.get("/round-table/recent")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data == []
