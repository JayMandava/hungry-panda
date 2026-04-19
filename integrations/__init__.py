"""
Hungry Panda Integrations

This module handles integrations with external services and protocols:
- MCP (Model Context Protocol) for Instagram connectivity
- Future: Other social media platforms, analytics services, etc.
"""

from integrations.mcp_client import (
    InstagramMCPClient,
    publish_content_via_mcp,
    sync_instagram_analytics,
    MCPConnectionConfig
)

__all__ = [
    "InstagramMCPClient",
    "publish_content_via_mcp",
    "sync_instagram_analytics",
    "MCPConnectionConfig"
]
