from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.http_probes import router


def _build_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestRoot:
    def test_returns_200(self):
        client = _build_client()
        res = client.get("/")
        assert res.status_code == 200

    def test_response_body_contains_expected_fields(self):
        client = _build_client()
        body = client.get("/").json()
        assert body["message"] == "Code Migration Code converting process API"
        assert body["version"] == "1.0.0"
        assert body["status"] == "running"
        assert "timestamp" in body
        assert "uptime_seconds" in body
        assert isinstance(body["uptime_seconds"], (int, float))


class TestHealth:
    def test_returns_200(self):
        client = _build_client()
        res = client.get("/health")
        assert res.status_code == 200

    def test_response_includes_message(self):
        client = _build_client()
        body = client.get("/health").json()
        assert body == {"message": "I'm alive!"}


class TestStartup:
    def test_returns_200(self):
        client = _build_client()
        res = client.get("/startup")
        assert res.status_code == 200

    def test_response_includes_running_message(self):
        client = _build_client()
        body = client.get("/startup").json()
        assert body["message"].startswith("Running for")
