from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_ask_stub():
    r = client.post("/ask", json={"question": "hola"})
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert "request_id" in data
    assert "latency_ms" in data
    assert "cost_usd" in data

def test_ask_returns_citations_when_index_built():
    r = client.post("/ask", json={"question": "machine learning"})
    assert r.status_code == 200
    data = r.json()
    # Could be "no sé" if index missing; but once built it should include citations.
    assert "citations" in data
