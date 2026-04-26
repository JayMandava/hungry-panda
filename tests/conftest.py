"""
Test configuration and fixtures for Hungry Panda tests.
"""
import pytest
from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def test_db_path(tmp_path):
    """Provide a temporary database path for testing."""
    return tmp_path / "test.db"


@pytest.fixture
def test_uploads_dir(tmp_path):
    """Provide a temporary uploads directory for testing."""
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    return uploads


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing."""
    monkeypatch.setenv("INSTAGRAM_USERNAME", "test_user")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080")
    monkeypatch.setenv("POSTING_METHOD", "manual")
