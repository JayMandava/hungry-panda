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
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Load environment variables from .env file
env_path = PROJECT_ROOT / "infra" / "config" / ".env"
if env_path.exists():
    load_dotenv(env_path)


class Config:
    """Application configuration loaded from environment variables"""
    
    # Server Settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8080"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Request limits
    # Maximum upload file size in MB (default 200MB for video uploads - reels need more)
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "200"))
    
    # CORS Settings
    # Comma-separated list of allowed origins. Use "*" for development only.
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")
    CORS_ALLOW_CREDENTIALS: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
    
    # Paths
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "hungry_panda.db"))
    UPLOADS_DIR: str = os.getenv("UPLOADS_DIR", str(PROJECT_ROOT / "uploads"))
    STATIC_DIR: str = str(PROJECT_ROOT / "static")
    
    # Instagram Account
    INSTAGRAM_USERNAME: Optional[str] = os.getenv("INSTAGRAM_USERNAME")
    INSTAGRAM_PASSWORD: Optional[str] = os.getenv("INSTAGRAM_PASSWORD")
    INSTAGRAM_ACCOUNT_TYPE: str = os.getenv("INSTAGRAM_ACCOUNT_TYPE", "personal")
    
    # Instagram API (for Business/Creator accounts)
    INSTAGRAM_APP_ID: Optional[str] = os.getenv("INSTAGRAM_APP_ID")
    INSTAGRAM_APP_SECRET: Optional[str] = os.getenv("INSTAGRAM_APP_SECRET")
    INSTAGRAM_ACCESS_TOKEN: Optional[str] = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    INSTAGRAM_REDIRECT_URI: Optional[str] = os.getenv("INSTAGRAM_REDIRECT_URI")
    INSTAGRAM_API_VERSION: str = os.getenv("INSTAGRAM_API_VERSION", "v25.0")
    
    # Facebook Login for Business → Instagram (new auth flow)
    # Falls back to INSTAGRAM_* if not explicitly set
    FACEBOOK_APP_ID: Optional[str] = os.getenv("FACEBOOK_APP_ID")
    FACEBOOK_APP_SECRET: Optional[str] = os.getenv("FACEBOOK_APP_SECRET")
    FACEBOOK_INSTAGRAM_REDIRECT_URI: Optional[str] = os.getenv("FACEBOOK_INSTAGRAM_REDIRECT_URI")
    
    # External APIs - LLM Configuration
    # OpenAI (legacy support)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    
    # Fireworks AI (Recommended - uses Kimi K2.5)
    FIREWORKS_API_KEY: Optional[str] = os.getenv("FIREWORKS_API_KEY")
    FIREWORKS_MODEL: str = os.getenv("FIREWORKS_MODEL", "accounts/fireworks/models/kimi-k2-5")
    FIREWORKS_BASE_URL: str = os.getenv("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")
    
    # LLM Provider Selection
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "fireworks")  # fireworks, openai, or none
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "10000"))
    
    # Posting Settings
    POSTING_METHOD: str = os.getenv("POSTING_METHOD", "manual")
    MAX_POSTS_PER_DAY: int = int(os.getenv("MAX_POSTS_PER_DAY", "3"))
    DEFAULT_TIMEZONE: str = os.getenv("DEFAULT_TIMEZONE", "local")
    
    # Scheduler
    AUTO_SCHEDULER_ENABLED: bool = os.getenv("AUTO_SCHEDULER_ENABLED", "false").lower() == "true"
    CHECK_INTERVAL_MINUTES: int = int(os.getenv("CHECK_INTERVAL_MINUTES", "5"))
    
    # MCP (Model Context Protocol) Integration
    ENABLE_MCP_INTEGRATION: bool = os.getenv("ENABLE_MCP_INTEGRATION", "false").lower() == "true"
    MCP_SERVER_TYPE: str = os.getenv("MCP_SERVER_TYPE", "ig-mcp")  # ig-mcp, instagram_dm_mcp
    MCP_SERVER_PATH: Optional[str] = os.getenv("MCP_SERVER_PATH")
    INSTAGRAM_BUSINESS_ACCOUNT_ID: Optional[str] = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    
    # Feature Flags
    ENABLE_COMPETITOR_TRACKING: bool = os.getenv("ENABLE_COMPETITOR_TRACKING", "true").lower() == "true"
    ENABLE_AUTO_CAPTIONS: bool = os.getenv("ENABLE_AUTO_CAPTIONS", "true").lower() == "true"
    ENABLE_AUTO_HASHTAGS: bool = os.getenv("ENABLE_AUTO_HASHTAGS", "true").lower() == "true"
    ENABLE_ANALYTICS: bool = os.getenv("ENABLE_ANALYTICS", "true").lower() == "true"
    
    # Phase 5: Remotion Renderer Feature Flag
    # When enabled, uses Remotion for video rendering instead of FFmpeg
    ENABLE_REMOTION_RENDERER: bool = os.getenv("ENABLE_REMOTION_RENDERER", "false").lower() == "true"
    REMOTION_OUTPUT_DIR: str = os.getenv("REMOTION_OUTPUT_DIR", str(PROJECT_ROOT / "remotion_output"))
    
    @classmethod
    def get_cors_origins(cls) -> list:
        """Parse CORS_ORIGINS string into a list of origins.
        
        Examples:
            "*" -> ["*"]
            "http://localhost:3000,https://example.com" -> ["http://localhost:3000", "https://example.com"]
        """
        origins = cls.CORS_ORIGINS.strip()
        if origins == "*":
            return ["*"]
        return [origin.strip() for origin in origins.split(",") if origin.strip()]
    
    @classmethod
    def validate(cls) -> dict:
        """Validate required configuration and return any issues"""
        issues = []
        warnings = []
        
        # CORS validation
        if cls.CORS_ORIGINS == "*" and not cls.DEBUG:
            warnings.append("CORS_ORIGINS is set to '*' (allow all) in production - this is a security risk")
        
        if not cls.INSTAGRAM_USERNAME:
            issues.append("INSTAGRAM_USERNAME not set - needed for tracking your account")
        
        # Validate posting method specific requirements
        if cls.POSTING_METHOD == "api" and not cls.INSTAGRAM_ACCESS_TOKEN:
            issues.append("INSTAGRAM_ACCESS_TOKEN required for API posting method")
        
        if cls.POSTING_METHOD == "browser" and (not cls.INSTAGRAM_USERNAME or not cls.INSTAGRAM_PASSWORD):
            issues.append("Instagram credentials required for browser automation")
        
        if cls.POSTING_METHOD == "mcp":
            if not cls.ENABLE_MCP_INTEGRATION:
                issues.append("ENABLE_MCP_INTEGRATION must be true when using MCP posting method")
            if not cls.INSTAGRAM_ACCESS_TOKEN:
                issues.append("INSTAGRAM_ACCESS_TOKEN required for MCP posting method")
            if not cls.MCP_SERVER_PATH:
                warnings.append("MCP_SERVER_PATH not set - will use default path")
        
        # MCP integration validation
        if cls.ENABLE_MCP_INTEGRATION:
            if cls.MCP_SERVER_TYPE not in ["ig-mcp", "instagram_dm_mcp"]:
                issues.append(f"Unsupported MCP server type: {cls.MCP_SERVER_TYPE}")
            
            if cls.MCP_SERVER_TYPE == "ig-mcp" and not cls.INSTAGRAM_ACCESS_TOKEN:
                issues.append("ig-mcp requires INSTAGRAM_ACCESS_TOKEN (Business/Creator account)")
            
            if cls.MCP_SERVER_TYPE == "instagram_dm_mcp" and (not cls.INSTAGRAM_USERNAME or not cls.INSTAGRAM_PASSWORD):
                issues.append("instagram_dm_mcp requires Instagram username and password")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }
    
    @classmethod
    def ensure_directories(cls):
        """Create required directories if they don't exist"""
        Path(cls.UPLOADS_DIR).mkdir(parents=True, exist_ok=True)
        Path(cls.STATIC_DIR).mkdir(parents=True, exist_ok=True)


# Create config instance
config = Config()
config.ensure_directories()
