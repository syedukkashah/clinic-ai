from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root_route():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Clinic AI backend is running"


def test_doctors_route():
    response = client.get("/doctors/")
    assert response.status_code == 200
    assert "doctors" in response.json()
