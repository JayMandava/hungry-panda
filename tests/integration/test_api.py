"""
Integration tests for the main FastAPI application.
"""
import pytest
from pathlib import Path

# Add project root to path
import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import FastAPI test client
from fastapi.testclient import TestClient

# Import the app - this will also initialize the database
# Use monkeypatch to set test environment


class TestHealthEndpoint:
    """Test suite for the /api/health endpoint."""
    
    @pytest.fixture
    def client(self, monkeypatch):
        """Create a test client with proper environment setup."""
        # Set required env vars
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("INSTAGRAM_USERNAME", "test_user")
        monkeypatch.setenv("CORS_ORIGINS", "*")
        
        # Import app fresh with new env vars
        from app.api.main import app
        
        return TestClient(app)
    
    def test_health_endpoint_returns_200(self, client):
        """Test that health endpoint returns 200 OK."""
        response = client.get("/api/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_health_endpoint_returns_version(self, client):
        """Test that health endpoint returns version info."""
        response = client.get("/api/health")
        data = response.json()
        
        assert "version" in data
        assert data["version"] == "1.0.0"
    
    def test_health_endpoint_returns_config_valid(self, client):
        """Test that health endpoint returns config validation status."""
        response = client.get("/api/health")
        data = response.json()
        
        assert "config_valid" in data
        assert isinstance(data["config_valid"], bool)


class TestDashboardEndpoint:
    """Test suite for the dashboard page endpoint."""
    
    @pytest.fixture
    def client(self, monkeypatch):
        """Create a test client with proper environment setup."""
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("INSTAGRAM_USERNAME", "test_user")
        monkeypatch.setenv("CORS_ORIGINS", "*")
        
        from app.api.main import app
        return TestClient(app)
    
    def test_dashboard_returns_200(self, client):
        """Test that dashboard endpoint returns 200 OK."""
        response = client.get("/")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    def test_dashboard_contains_title(self, client):
        """Test that dashboard HTML contains expected title."""
        response = client.get("/")
        
        assert "Hungry Panda" in response.text


class TestUploadPageEndpoint:
    """Test suite for the upload page endpoint."""
    
    @pytest.fixture
    def client(self, monkeypatch):
        """Create a test client with proper environment setup."""
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("INSTAGRAM_USERNAME", "test_user")
        monkeypatch.setenv("CORS_ORIGINS", "*")
        
        from app.api.main import app
        return TestClient(app)
    
    def test_upload_page_returns_200(self, client):
        """Test that upload page endpoint returns 200 OK."""
        response = client.get("/upload")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestCORSHeaders:
    """Test suite for CORS configuration."""
    
    @pytest.fixture
    def client(self, monkeypatch):
        """Create a test client with CORS configured."""
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("INSTAGRAM_USERNAME", "test_user")
        monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
        
        from app.api.main import app
        return TestClient(app)
    
    def test_cors_headers_present_on_health(self, client):
        """Test that CORS headers are present on responses."""
        response = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
        
        assert "access-control-allow-origin" in response.headers
