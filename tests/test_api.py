import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")
TestClient = fastapi_testclient.TestClient

from src.api import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_features_endpoint_has_delivery_statuses():
    response = client.get("/features")
    assert response.status_code == 200
    payload = response.json()
    assert payload["counts"]["done"] >= 1
    assert any(item["item"] == "Alerts" for item in payload["features"])


def test_alert_rules_endpoint_documents_alert_types():
    response = client.get("/alerts/rules")
    assert response.status_code == 200
    payload = response.json()
    assert "realtime_move_threshold_pct" in payload["rules"]
    assert len(payload["types"]) == 3
