"""
Unit tests for configuration module.
"""
import pytest
from pathlib import Path

# We need to import after setting up the path in conftest
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from infra.config.settings import Config


class TestConfig:
    """Test suite for Config class."""
    
    def test_cors_origins_parsing_wildcard(self, mock_env_vars):
        """Test that CORS_ORIGINS='*' returns ['*']."""
        import os
        os.environ["CORS_ORIGINS"] = "*"
        # Need to reimport to get fresh config
        from importlib import reload
        import infra.config.settings as settings_module
        reload(settings_module)
        
        origins = settings_module.Config.get_cors_origins()
        assert origins == ["*"]
    
    def test_cors_origins_parsing_multiple(self, mock_env_vars):
        """Test that comma-separated origins are parsed correctly."""
        import os
        os.environ["CORS_ORIGINS"] = "http://localhost:3000,https://example.com"
        
        from importlib import reload
        import infra.config.settings as settings_module
        reload(settings_module)
        
        origins = settings_module.Config.get_cors_origins()
        assert origins == ["http://localhost:3000", "https://example.com"]
    
    def test_cors_origins_parsing_single(self, mock_env_vars):
        """Test that single origin is parsed correctly."""
        import os
        os.environ["CORS_ORIGINS"] = "http://localhost:3000"
        
        from importlib import reload
        import infra.config.settings as settings_module
        reload(settings_module)
        
        origins = settings_module.Config.get_cors_origins()
        assert origins == ["http://localhost:3000"]
    
    def test_validate_returns_dict(self, mock_env_vars):
        """Test that validate() returns expected dict structure."""
        result = Config.validate()
        
        assert isinstance(result, dict)
        assert "valid" in result
        assert "issues" in result
        assert "warnings" in result
        assert isinstance(result["valid"], bool)
        assert isinstance(result["issues"], list)
        assert isinstance(result["warnings"], list)


class TestConfigPaths:
    """Test suite for config path settings."""
    
    def test_default_uploads_dir(self):
        """Test default uploads directory path."""
        # The path should be absolute and contain "uploads"
        assert "uploads" in Config.UPLOADS_DIR.lower()
    
    def test_database_path_default(self):
        """Test default database path."""
        assert "hungry_panda" in Config.DATABASE_PATH.lower()
        assert Config.DATABASE_PATH.endswith(".db")
