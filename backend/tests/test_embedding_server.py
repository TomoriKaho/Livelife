import threading

from fastapi.testclient import TestClient

from app.embedding_server import app
from app.services.retrieval.config import RetrievalSettings


def test_model_service_auth_busy_limits_and_response(monkeypatch):
    class Vector:
        def tolist(self):
            return [1.0, 0.0, 0.0]

    class Encoder:
        def encode(self, inputs, **kwargs):
            assert inputs == ["公开资料"]
            return [Vector()]

    monkeypatch.setattr(app.state, "encoder", Encoder(), raising=False)
    monkeypatch.setattr(app.state, "lock", threading.Lock(), raising=False)
    monkeypatch.setattr(
        app.state,
        "settings",
        RetrievalSettings(
            model="test-model",
            model_revision="test-revision",
            api_key="test-only-key",
            dimensions=3,
        ),
        raising=False,
    )
    # No lifespan: this contract test deliberately does not import/download torch or weights.
    client = TestClient(app)
    body = {"model": "test-model", "input": ["公开资料"]}
    assert client.post("/v1/embeddings", json=body).status_code == 401
    client.headers["Authorization"] = "Bearer test-only-key"
    assert client.post("/v1/embeddings", json={**body, "model": "wrong"}).status_code == 400
    assert client.post("/v1/embeddings", json={**body, "input": ["x"] * 17}).status_code == 422
    assert client.post("/v1/embeddings", json={**body, "input": ["x" * 8001]}).status_code == 422
    app.state.lock.acquire()
    try:
        assert client.post("/v1/embeddings", json=body).status_code == 429
    finally:
        app.state.lock.release()
    response = client.post("/v1/embeddings", json=body)
    assert response.status_code == 200
    assert response.json() == {
        "model": "test-model",
        "revision": "test-revision",
        "data": [{"object": "embedding", "index": 0, "embedding": [1.0, 0.0, 0.0]}],
    }
    assert not app.state.lock.locked()
    assert client.get("/health").json()["revision"] == "test-revision"
