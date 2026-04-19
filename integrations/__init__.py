"""
Hungry Panda Integrations

This module handles integrations with external services and protocols:
- MCP (Model Context Protocol) for Instagram connectivity
- LLM providers (Fireworks AI, OpenAI) for AI content generation
- Future: Other social media platforms, analytics services, etc.
"""

from integrations.mcp_client import (
    InstagramMCPClient,
    publish_content_via_mcp,
    sync_instagram_analytics,
    MCPConnectionConfig
)

from integrations.llm_client import (
    LLMClient,
    LLMError,
    generate_caption,
    generate_hashtags
)

__all__ = [
    # MCP
    "InstagramMCPClient",
    "publish_content_via_mcp",
    "sync_instagram_analytics",
    "MCPConnectionConfig",
    # LLM
    "LLMClient",
    "LLMError",
    "generate_caption",
    "generate_hashtags"
]
