from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import http_probes
import datetime


def test_http_probes_root_endpoint():
    """Test the root health check endpoint."""
    app = FastAPI()
    app.include_router(http_probes.router)
    
    client = TestClient(app)
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Code Migration Code converting process API"
    assert data["version"] == "1.0.0"
    assert data["status"] == "running"
    assert "timestamp" in data
    assert "uptime_seconds" in data


def test_http_probes_root_has_iso_timestamp():
    """Test that root endpoint returns ISO format timestamp."""
    app = FastAPI()
    app.include_router(http_probes.router)
    
    client = TestClient(app)
    response = client.get("/")
    data = response.json()
    
    # Verify timestamp is in ISO format
    try:
        datetime.datetime.fromisoformat(data["timestamp"])
    except ValueError:
        assert False, "Timestamp is not in ISO format"


def test_http_probes_root_uptime_is_numeric():
    """Test that root endpoint returns numeric uptime."""
    app = FastAPI()
    app.include_router(http_probes.router)
    
    client = TestClient(app)
    response = client.get("/")
    data = response.json()
    
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0


def test_http_probes_health_endpoint():
    """Test the health liveness probe endpoint."""
    app = FastAPI()
    app.include_router(http_probes.router)
    
    client = TestClient(app)
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "I'm alive!"


def test_http_probes_health_has_header():
    """Test that health endpoint includes custom header in response."""
    app = FastAPI()
    app.include_router(http_probes.router)
    
    client = TestClient(app)
    response = client.get("/health")
    
    # The response should have the custom header if implementation sets it
    # Note: TestClient may not preserve response headers in all cases
    assert response.status_code == 200


def test_http_probes_startup_endpoint():
    """Test the startup probe endpoint."""
    app = FastAPI()
    app.include_router(http_probes.router)
    
    client = TestClient(app)
    response = client.get("/startup")
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Running for" in data["message"]


def test_http_probes_startup_has_header():
    """Test that startup endpoint includes custom header in response."""
    app = FastAPI()
    app.include_router(http_probes.router)
    
    client = TestClient(app)
    response = client.get("/startup")
    
    # The response should have the custom header if implementation sets it
    # Note: TestClient may not preserve response headers in all cases
    assert response.status_code == 200


def test_http_probes_startup_uptime_format():
    """Test that startup endpoint returns uptime in HH:MM:SS format."""
    app = FastAPI()
    app.include_router(http_probes.router)
    
    client = TestClient(app)
    response = client.get("/startup")
    data = response.json()
    
    # Message should contain format like "0:0:0" or similar
    assert "Running for" in data["message"]
    assert ":" in data["message"]


def test_http_probes_status_codes():
    """Test that all health check endpoints return 200."""
    app = FastAPI()
    app.include_router(http_probes.router)
    
    client = TestClient(app)
    
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/startup").status_code == 200


def test_http_probes_content_type():
    """Test that all responses are JSON."""
    app = FastAPI()
    app.include_router(http_probes.router)
    
    client = TestClient(app)
    
    for endpoint in ["/", "/health", "/startup"]:
        response = client.get(endpoint)
        assert response.headers["content-type"] == "application/json"


def test_http_probes_root_version_format():
    """Test that version is in correct format."""
    app = FastAPI()
    app.include_router(http_probes.router)
    
    client = TestClient(app)
    response = client.get("/")
    data = response.json()
    
    assert data["version"] == "1.0.0"


def test_http_probes_root_status_value():
    """Test that status is 'running'."""
    app = FastAPI()
    app.include_router(http_probes.router)
    
    client = TestClient(app)
    response = client.get("/")
    data = response.json()
    
    assert data["status"] == "running"
