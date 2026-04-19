"""
Hungry Panda - Instagram Growth Agent
Configuration management using environment variables and .env files
"""
import os
from pathlib import Path
from typing import Optional

# Load .env if exists
from dotenv import load_dotenv

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Load environment variables from .env file
env_path = PROJECT_ROOT / "config" / ".env"
if env_path.exists():
    load_dotenv(env_path)


class Config:
    """Application configuration loaded from environment variables"""
    
    # Server Settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Paths
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "hungry_panda.db"))
    UPLOADS_DIR: str = str(PROJECT_ROOT / "uploads")
    STATIC_DIR: str = str(PROJECT_ROOT / "static")
    
    # Instagram Account
    INSTAGRAM_USERNAME: Optional[str] = os.getenv("INSTAGRAM_USERNAME")
    INSTAGRAM_PASSWORD: Optional[str] = os.getenv("INSTAGRAM_PASSWORD")
    INSTAGRAM_ACCOUNT_TYPE: str = os.getenv("INSTAGRAM_ACCOUNT_TYPE", "personal")
    
    # Instagram API (for Business/Creator accounts)
    INSTAGRAM_APP_ID: Optional[str] = os.getenv("INSTAGRAM_APP_ID")
    INSTAGRAM_APP_SECRET: Optional[str] = os.getenv("INSTAGRAM_APP_SECRET")
    INSTAGRAM_ACCESS_TOKEN: Optional[str] = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    
    # External APIs
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    
    # Posting Settings
    POSTING_METHOD: str = os.getenv("POSTING_METHOD", "manual")
    MAX_POSTS_PER_DAY: int = int(os.getenv("MAX_POSTS_PER_DAY", "3"))
    DEFAULT_TIMEZONE: str = os.getenv("DEFAULT_TIMEZONE", "local")
    
    # Scheduler
    AUTO_SCHEDULER_ENABLED: bool = os.getenv("AUTO_SCHEDULER_ENABLED", "false").lower() == "true"
    CHECK_INTERVAL_MINUTES: int = int(os.getenv("CHECK_INTERVAL_MINUTES", "5"))
    
    # Feature Flags
    ENABLE_COMPETITOR_TRACKING: bool = os.getenv("ENABLE_COMPETITOR_TRACKING", "true").lower() == "true"
    ENABLE_AUTO_CAPTIONS: bool = os.getenv("ENABLE_AUTO_CAPTIONS", "true").lower() == "true"
    ENABLE_AUTO_HASHTAGS: bool = os.getenv("ENABLE_AUTO_HASHTAGS", "true").lower() == "true"
    ENABLE_ANALYTICS: bool = os.getenv("ENABLE_ANALYTICS", "true").lower() == "true"
    
    @classmethod
    def validate(cls) -> dict:
        """Validate required configuration and return any issues"""
        issues = []
        
        if not cls.INSTAGRAM_USERNAME:
            issues.append("INSTAGRAM_USERNAME not set - needed for tracking your account")
        
        if cls.POSTING_METHOD == "api" and not cls.INSTAGRAM_ACCESS_TOKEN:
            issues.append("INSTAGRAM_ACCESS_TOKEN required for API posting method")
        
        if cls.POSTING_METHOD == "browser" and (not cls.INSTAGRAM_USERNAME or not cls.INSTAGRAM_PASSWORD):
            issues.append("Instagram credentials required for browser automation")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }
    
    @classmethod
    def ensure_directories(cls):
        """Create required directories if they don't exist"""
        Path(cls.UPLOADS_DIR).mkdir(parents=True, exist_ok=True)
        Path(cls.STATIC_DIR).mkdir(parents=True, exist_ok=True)


# Create config instance
config = Config()
config.ensure_directories()
