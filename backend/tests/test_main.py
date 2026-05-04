from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_root_route():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_doctors_route():
    response = client.get("/api/doctors/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
