"""
Unit tests for JARVIS FastAPI Backend & HUD Bridge (Tier 4)
"""

import pytest
from fastapi.testclient import TestClient
from jarvis.server.app import create_app
from jarvis.brain.agent import JarvisAgent


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_server_status_endpoint(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "JARVIS" in data["name"]
    assert "telemetry" in data


def test_server_telemetry_endpoint(client):
    response = client.get("/api/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert "cpu_percent" in data
    assert "ram_percent" in data
    assert "disk_percent" in data


def test_server_history_and_reset(client):
    # Test history retrieval
    resp_hist = client.get("/api/history")
    assert resp_hist.status_code == 200
    assert "history" in resp_hist.json()

    # Test memory reset
    resp_reset = client.post("/api/reset")
    assert resp_reset.status_code == 200
    assert resp_reset.json()["status"] == "success"


def test_server_rest_chat(client):
    response = client.post("/api/chat", json={"message": "Open calculator", "voice": False})
    assert response.status_code == 200
    data = response.json()
    assert "Opening Calculator" in data["content"]


def test_serve_hud_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "J.A.R.V.I.S." in response.text
    assert "arc-reactor-canvas" in response.text
