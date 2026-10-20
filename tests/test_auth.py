import pytest
from fastapi.testclient import TestClient
from tests.conftest import TEST_SECRET


def test_reject_unauthenticated_request(client: TestClient):
    payload = {"ticker": "BTCUSDT", "action": "BUY", "price": 60000}
    response = client.post("/webhook", json=payload)
    assert response.status_code == 401
    assert "Unauthorized" in response.json()["detail"]


def test_reject_wrong_secret(client: TestClient):
    payload = {"ticker": "BTCUSDT", "action": "BUY", "passphrase": "wrong_password"}
    response = client.post("/webhook", json=payload)
    assert response.status_code == 401


def test_auth_via_json_passphrase(client: TestClient):
    payload = {
        "passphrase": TEST_SECRET,
        "ticker": "BTCUSDT",
        "action": "BUY",
        "price": 67000.0,
    }
    response = client.post("/webhook", json=payload)
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["ticker"] == "BTCUSDT"


def test_auth_via_query_parameter(client: TestClient):
    payload = {"ticker": "ETHUSDT", "action": "SELL", "price": 3500.0}
    response = client.post(f"/webhook?secret={TEST_SECRET}", json=payload)
    assert response.status_code == 202
    assert response.json()["ticker"] == "ETHUSDT"


def test_auth_via_header(client: TestClient):
    payload = {"ticker": "SOLUSDT", "action": "BUY", "price": 180.0}
    headers = {"X-Webhook-Secret": TEST_SECRET}
    response = client.post("/webhook", json=payload, headers=headers)
    assert response.status_code == 202
    assert response.json()["ticker"] == "SOLUSDT"


def test_auth_via_path_token(client: TestClient):
    payload = {"ticker": "BNBUSDT", "action": "BUY", "price": 590.0}
    response = client.post(f"/webhook/{TEST_SECRET}", json=payload)
    assert response.status_code == 202
    assert response.json()["ticker"] == "BNBUSDT"


def test_auth_via_path_token_invalid(client: TestClient):
    payload = {"ticker": "BNBUSDT", "action": "BUY", "price": 590.0}
    response = client.post("/webhook/invalid_secret_token", json=payload)
    assert response.status_code == 401
