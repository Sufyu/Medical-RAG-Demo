from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_query():
    response = client.post("/query", json={"question": "What is the treatment for hypertension?", "top_k": 3})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "latency_ms" in data
    assert data["question"] == "What is the treatment for hypertension?"
    assert len(data["chunks"]) == 3

def test_query_invalid_top_k():
    response = client.post("/query", json={"question": "What is the treatment for hypertension?", "top_k": 0})
    assert response.status_code == 422  # Unprocessable Entity due to validation error
    data = response.json()

def test_query_invalid_question_length():
    response = client.post("/query", json={"question": "Hi", "top_k": 3})
    assert response.status_code == 422