import pytest
from fastapi.testclient import TestClient
from app.api import app

def test_health_check():
    client = TestClient(app)
    response = client.get("/users/me/")
    # Ожидается 401, если не передан токен (API живой и отвечает)
    assert response.status_code in (200, 401)

def test_register():
    client = TestClient(app)
    response = client.post("/register", json={
        "username": "testuser1",
        "email": "testuser1@example.com",
        "password": "testpass123"
    })
    assert response.status_code in (200, 400, 409)  # 400/409 если пользователь уже есть

def test_predictions_unauthorized():
    client = TestClient(app)
    response = client.get("/predictions/")
    assert response.status_code == 401 