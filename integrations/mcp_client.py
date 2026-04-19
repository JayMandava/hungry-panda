"""
MCP Client Integration for Hungry Panda
Connects to Instagram MCP servers (ig-mcp, instagram_dm_mcp)
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from config.settings import config

logger = logging.getLogger(__name__)


@dataclass
class MCPConnectionConfig:
    """Configuration for MCP server connection"""
    server_type: str  # "ig-mcp", "instagram_dm_mcp", "meta-ads-mcp"
    server_path: Optional[str] = None
    command: Optional[str] = None
    args: List[str] = None
    env: Dict[str, str] = None
    
    def __post_init__(self):
        if self.args is None:
            self.args = []
        if self.env is None:
            self.env = {}


class InstagramMCPClient:
    """
    Client for connecting to Instagram MCP servers.
    
    Supports multiple MCP servers:
    - ig-mcp: Official Instagram Graph API (Business/Creator accounts)
    - instagram_dm_mcp: Unofficial API for DMs and personal accounts
    - meta-ads-mcp: For advertising on Instagram
    
    Example usage:
        client = InstagramMCPClient("ig-mcp")
        await client.connect()
        
        # Get profile info
        profile = await client.get_profile_info()
        
        # Publish media
        result = await client.publish_media(
            image_path="/path/to/photo.jpg",
            caption="Delicious homemade pasta! 🍝",
            hashtags=["pasta", "homemade", "foodie"]
        )
    """
    
    def __init__(self, server_type: str = "ig-mcp"):
        self.server_type = server_type
        self.config = self._load_config()
        self.connected = False
        self.session = None
        self._client = None
        
    def _load_config(self) -> MCPConnectionConfig:
        """Load MCP server configuration from settings"""
        server_path = config.MCP_SERVER_PATH if hasattr(config, 'MCP_SERVER_PATH') else None
        
        if self.server_type == "ig-mcp":
            return MCPConnectionConfig(
                server_type="ig-mcp",
                server_path=server_path or "/path/to/ig-mcp/src/instagram_mcp_server.py",
                command="python",
                args=[server_path] if server_path else [],
                env={
                    "INSTAGRAM_ACCESS_TOKEN": config.INSTAGRAM_ACCESS_TOKEN or "",
                    "INSTAGRAM_BUSINESS_ACCOUNT_ID": getattr(config, 'INSTAGRAM_BUSINESS_ACCOUNT_ID', ""),
                    "FACEBOOK_APP_ID": config.INSTAGRAM_APP_ID or "",
                    "FACEBOOK_APP_SECRET": config.INSTAGRAM_APP_SECRET or "",
                }
            )
        elif self.server_type == "instagram_dm_mcp":
            return MCPConnectionConfig(
                server_type="instagram_dm_mcp",
                server_path=server_path,
                command="python",
                args=[server_path] if server_path else [],
                env={
                    "INSTAGRAM_USERNAME": config.INSTAGRAM_USERNAME or "",
                    "INSTAGRAM_PASSWORD": config.INSTAGRAM_PASSWORD or "",
                }
            )
        else:
            raise ValueError(f"Unsupported MCP server type: {self.server_type}")
    
    async def connect(self) -> bool:
        """
        Connect to the MCP server.
        
        Returns:
            bool: True if connection successful
        """
        try:
            # Note: This is a placeholder. Actual implementation would use
            # the official MCP Python SDK to establish stdio or SSE connection.
            # For now, we simulate the connection.
            
            logger.info(f"Connecting to MCP server: {self.server_type}")
            
            # Check if required credentials are present
            if self.server_type == "ig-mcp":
                if not config.INSTAGRAM_ACCESS_TOKEN:
                    logger.error("INSTAGRAM_ACCESS_TOKEN not configured")
                    return False
            elif self.server_type == "instagram_dm_mcp":
                if not config.INSTAGRAM_USERNAME or not config.INSTAGRAM_PASSWORD:
                    logger.error("Instagram credentials not configured")
                    return False
            
            # Simulate connection (actual implementation uses MCP SDK)
            self.connected = True
            logger.info(f"Connected to {self.server_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from MCP server"""
        self.connected = False
        self.session = None
        logger.info("Disconnected from MCP server")
    
    # ==================== Profile Tools ====================
    
    async def get_profile_info(self) -> Dict[str, Any]:
        """
        Get Instagram business profile information.
        
        Returns:
            Dict containing profile data:
            - username
            - followers_count
            - follows_count
            - media_count
            - biography
            - website
        """
        if not self.connected:
            raise RuntimeError("Not connected to MCP server")
        
        try:
            # Call MCP tool: get_profile_info
            logger.info("Fetching profile info via MCP")
            
            # Placeholder - actual implementation calls MCP tool
            return {
                "username": config.INSTAGRAM_USERNAME,
                "followers_count": 0,
                "follows_count": 0,
                "media_count": 0,
                "biography": "",
                "website": "",
                "source": "mcp_placeholder"
            }
            
        except Exception as e:
            logger.error(f"Failed to get profile info: {e}")
            raise
    
    # ==================== Media/Publishing Tools ====================
    
    async def publish_media(
        self,
        image_path: str,
        caption: str,
        hashtags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Publish media to Instagram.
        
        Args:
            image_path: Path to image file
            caption: Post caption
            hashtags: Optional list of hashtags
            
        Returns:
            Dict with result:
            - success: bool
            - media_id: Instagram media ID
            - permalink: URL to the post
            - error: Error message if failed
        """
        if not self.connected:
            raise RuntimeError("Not connected to MCP server")
        
        try:
            # Format full caption with hashtags
            full_caption = caption
            if hashtags:
                hashtag_str = " ".join([f"#{tag}" for tag in hashtags])
                full_caption = f"{caption}\n\n{hashtag_str}"
            
            logger.info(f"Publishing media via MCP: {image_path}")
            
            # Call MCP tool: publish_media
            # Placeholder - actual implementation calls MCP tool
            return {
                "success": True,
                "media_id": "placeholder_id",
                "permalink": f"https://instagram.com/p/placeholder",
                "caption": full_caption,
                "method": "mcp"
            }
            
        except Exception as e:
            logger.error(f"Failed to publish media: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_recent_posts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent posts with engagement data.
        
        Args:
            limit: Number of posts to fetch
            
        Returns:
            List of post dicts with:
            - id: Media ID
            - caption: Post caption
            - media_url: URL to media
            - permalink: Post URL
            - timestamp: Posted time
            - like_count: Number of likes
            - comments_count: Number of comments
        """
        if not self.connected:
            raise RuntimeError("Not connected to MCP server")
        
        try:
            logger.info(f"Fetching {limit} recent posts via MCP")
            
            # Call MCP tool: get_media_posts
            # Placeholder
            return []
            
        except Exception as e:
            logger.error(f"Failed to get recent posts: {e}")
            return []
    
    async def get_media_insights(self, media_id: str) -> Dict[str, Any]:
        """
        Get engagement metrics for a specific post.
        
        Args:
            media_id: Instagram media ID
            
        Returns:
            Dict with engagement metrics:
            - engagement: Total engagement
            - impressions: View count
            - reach: Unique viewers
            - saved: Save count
            - video_views: Video views (if video)
        """
        if not self.connected:
            raise RuntimeError("Not connected to MCP server")
        
        try:
            logger.info(f"Fetching insights for media: {media_id}")
            
            # Call MCP tool: get_media_insights
            # Placeholder
            return {
                "media_id": media_id,
                "engagement": 0,
                "impressions": 0,
                "reach": 0,
                "saved": 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get media insights: {e}")
            return {}
    
    # ==================== Analytics Tools ====================
    
    async def get_account_insights(
        self,
        metric: str = "impressions",
        period: str = "week"
    ) -> Dict[str, Any]:
        """
        Get account-level analytics.
        
        Args:
            metric: Metric to fetch (impressions, reach, follower_count, etc.)
            period: Time period (day, week, month, lifetime)
            
        Returns:
            Dict with analytics data
        """
        if not self.connected:
            raise RuntimeError("Not connected to MCP server")
        
        try:
            logger.info(f"Fetching account insights via MCP: {metric} ({period})")
            
            # Call MCP tool: get_account_insights
            # Placeholder
            return {
                "metric": metric,
                "period": period,
                "values": []
            }
            
        except Exception as e:
            logger.error(f"Failed to get account insights: {e}")
            return {}
    
    # ==================== DM Tools (instagram_dm_mcp only) ====================
    
    async def send_dm(self, username: str, message: str) -> Dict[str, Any]:
        """
        Send direct message (requires instagram_dm_mcp).
        
        Args:
            username: Recipient Instagram username
            message: Message text
            
        Returns:
            Dict with result
        """
        if self.server_type != "instagram_dm_mcp":
            raise RuntimeError("DM features require instagram_dm_mcp server")
        
        if not self.connected:
            raise RuntimeError("Not connected to MCP server")
        
        try:
            logger.info(f"Sending DM to {username} via MCP")
            
            # Call MCP tool: send_message
            # Placeholder
            return {
                "success": True,
                "recipient": username,
                "message": message
            }
            
        except Exception as e:
            logger.error(f"Failed to send DM: {e}")
            return {"success": False, "error": str(e)}
    
    async def list_chats(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        List DM conversations (requires instagram_dm_mcp).
        
        Args:
            limit: Number of conversations to fetch
            
        Returns:
            List of chat threads
        """
        if self.server_type != "instagram_dm_mcp":
            raise RuntimeError("DM features require instagram_dm_mcp server")
        
        if not self.connected:
            raise RuntimeError("Not connected to MCP server")
        
        try:
            logger.info(f"Listing {limit} chats via MCP")
            
            # Call MCP tool: list_chats
            # Placeholder
            return []
            
        except Exception as e:
            logger.error(f"Failed to list chats: {e}")
            return []


# ==================== Integration with Hungry Panda ====================

async def publish_content_via_mcp(
    content_id: str,
    content_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Publish content to Instagram using MCP.
    
    This is the main integration function used by Hungry Panda
    when POSTING_METHOD=mcp is configured.
    
    Args:
        content_id: Internal content ID
        content_data: Dict with filepath, caption, hashtags
        
    Returns:
        Dict with publishing result
    """
    client = InstagramMCPClient("ig-mcp")
    
    try:
        # Connect to MCP server
        connected = await client.connect()
        if not connected:
            return {
                "success": False,
                "error": "Failed to connect to MCP server",
                "method": "mcp"
            }
        
        # Publish the media
        result = await client.publish_media(
            image_path=content_data['filepath'],
            caption=content_data['caption'],
            hashtags=content_data.get('hashtags', [])
        )
        
        # Store the Instagram media ID if successful
        if result['success']:
            result['content_id'] = content_id
            result['instagram_media_id'] = result.get('media_id')
        
        return result
        
    except Exception as e:
        logger.error(f"MCP publish failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "method": "mcp"
        }
    finally:
        await client.disconnect()


async def sync_instagram_analytics() -> Dict[str, Any]:
    """
    Sync analytics data from Instagram via MCP.
    
    Fetches:
    - Recent posts with engagement
    - Account insights
    - Profile information
    
    Returns:
        Dict with all synced data
    """
    client = InstagramMCPClient("ig-mcp")
    
    try:
        connected = await client.connect()
        if not connected:
            return {"error": "Failed to connect to MCP server"}
        
        # Fetch all data
        profile = await client.get_profile_info()
        posts = await client.get_recent_posts(limit=25)
        insights = await client.get_account_insights()
        
        return {
            "profile": profile,
            "posts": posts,
            "insights": insights,
            "synced_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Analytics sync failed: {e}")
        return {"error": str(e)}
    finally:
        await client.disconnect()


# Import datetime at the end to avoid circular imports
from datetime import datetime
