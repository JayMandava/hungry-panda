# Instagram MCP Integration for Hungry Panda

This guide explains how to integrate Instagram MCP (Model Context Protocol) servers with Hungry Panda for enhanced functionality.

## What is MCP?

**Model Context Protocol (MCP)** is an open protocol by Anthropic that standardizes how AI systems connect to external data sources and tools. Think of it like "USB-C for AI applications" - it provides a universal way to connect AI assistants to various services.

## Available Instagram MCP Servers

### 1. **ig-mcp** (Recommended for Business Accounts)
**Repo:** `jlbadano/ig-mcp` (⭐ 117 stars)

**Features:**
- ✅ Official Instagram Graph API (safe & reliable)
- ✅ Get profile info, media posts, insights
- ✅ Publish photos/videos to Instagram
- ✅ Get engagement metrics
- ✅ DM support (with Advanced Access)
- ✅ Rate limiting & error handling

**Best for:** Business/Creator accounts that want official API access

**Requirements:**
- Instagram Business or Creator account
- Facebook Business Page connection
- Meta Developer App with permissions

---

### 2. **instagram_dm_mcp** (For Personal Accounts)
**Repo:** `trypeggy/instagram_dm_mcp` (⭐ 160 stars)

**Features:**
- ✅ Send/receive DMs
- ✅ List chats and messages
- ✅ Download media from DMs
- ✅ Get user info, followers, following
- ✅ Like posts
- ✅ Browser automation approach

**Best for:** Personal accounts needing DM automation

**Requirements:**
- Instagram username/password
- Personal account works

**⚠️ Warning:** Uses unofficial API (higher ban risk)

---

### 3. **meta-ads-mcp** (For Advertising)
**Repo:** `pipeboard-co/meta-ads-mcp` (⭐ 793 stars)

**Features:**
- ✅ Manage Facebook & Instagram Ads
- ✅ Create and monitor ad campaigns
- ✅ Ad analytics and reporting

**Best for:** Running paid promotion on Instagram

---

## Integration Options for Hungry Panda

### Option A: Use MCP as External Tool (Recommended)

Keep Hungry Panda as the main system, but use MCP servers for specific Instagram operations.

**Architecture:**
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Hungry Panda   │────▶│   MCP Client    │────▶│  ig-mcp Server  │
│   Dashboard     │     │  (stdio/sse)    │     │  (Graph API)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                               │
        │                                               │
        ▼                                               ▼
┌─────────────────┐                          ┌─────────────────┐
│  Local Database │                          │   Instagram   │
│   (Strategy)    │                          │     API       │
└─────────────────┘                          └─────────────────┘
```

**Benefits:**
- Hungry Panda manages strategy, content, scheduling
- MCP handles actual Instagram API calls
- Clean separation of concerns
- Can swap MCP servers as needed

---

### Option B: Add MCP Server Mode to Hungry Panda

Convert Hungry Panda into an MCP server itself.

**Use case:** Allow other AI assistants (Claude, Cursor, etc.) to use Hungry Panda's features.

**MCP Tools to expose:**
- `analyze_content` - Upload and analyze food photos
- `generate_caption` - Create optimized captions
- `get_strategy` - Get weekly content strategy
- `schedule_post` - Schedule content for posting
- `track_competitor` - Add competitor tracking
- `get_analytics` - Get growth metrics

**Benefits:**
- Other AI tools can leverage Hungry Panda
- Ecosystem integration
- Use with Claude Desktop, Cursor, etc.

---

## Setup Guide: ig-mcp Integration

### Step 1: Set up ig-mcp Server

```bash
# Clone the MCP server
git clone https://github.com/jlbadano/ig-mcp.git
cd ig-mcp

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env.example .env
```

### Step 2: Get Instagram API Credentials

1. **Convert to Business Account**
   - Instagram app → Settings → Account → Switch to Professional Account
   - Choose "Business" and complete setup

2. **Connect Facebook Page**
   - Settings → Account → Linked Accounts → Facebook
   - Connect/create a Facebook Page

3. **Create Facebook App**
   - Go to [developers.facebook.com](https://developers.facebook.com)
   - Create new app → Choose "Business"
   - Add "Instagram Graph API" product

4. **Get Access Token**
   - Use Graph API Explorer
   - Generate long-lived token (valid 60 days)
   - See [AUTHENTICATION_GUIDE.md](https://github.com/jlbadano/ig-mcp/blob/main/AUTHENTICATION_GUIDE.md)

### Step 3: Update Hungry Panda Config

Add to `config/.env`:

```env
# MCP Integration
ENABLE_MCP_INTEGRATION=true
MCP_SERVER_TYPE=ig-mcp
MCP_SERVER_PATH=/path/to/ig-mcp/src/instagram_mcp_server.py

# Instagram API (for MCP)
INSTAGRAM_ACCESS_TOKEN=your_long_lived_token
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_account_id
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
```

### Step 4: Connect Hungry Panda to MCP

We've added an MCP client module to Hungry Panda:

```python
# Example usage in Hungry Panda
from integrations.mcp_client import InstagramMCPClient

# Initialize MCP client
mcp = InstagramMCPClient()

# When content is ready to post
async def post_to_instagram(content_id: str):
    # Get content from database
    content = get_content(content_id)
    
    # Use MCP to publish
    result = await mcp.publish_media(
        image_path=content['filepath'],
        caption=content['caption'] + '\n\n' + format_hashtags(content['hashtags'])
    )
    
    if result['success']:
        mark_as_posted(content_id, result['media_id'])
```

---

## Implementation: MCP Client Module

We've created a new module for Hungry Panda:

```python
# integrations/mcp_client.py
"""
MCP Client for Instagram integration
Supports both ig-mcp (Graph API) and instagram_dm_mcp (private API)
"""

import asyncio
import json
from typing import Dict, List, Optional
from config.settings import config


class InstagramMCPClient:
    """Client for connecting to Instagram MCP servers"""
    
    def __init__(self, server_type: str = "ig-mcp"):
        self.server_type = server_type
        self.server_path = config.MCP_SERVER_PATH
        self.connected = False
    
    async def connect(self):
        """Initialize connection to MCP server"""
        # Implementation using MCP Python SDK
        # Connects via stdio or SSE transport
        pass
    
    async def get_profile_info(self) -> Dict:
        """Get Instagram business profile information"""
        # Call MCP tool: get_profile_info
        pass
    
    async def publish_media(
        self, 
        image_path: str, 
        caption: str,
        hashtags: Optional[List[str]] = None
    ) -> Dict:
        """
        Publish media to Instagram
        
        Returns:
            {
                'success': bool,
                'media_id': str,
                'permalink': str
            }
        """
        # Call MCP tool: publish_media
        pass
    
    async def get_media_insights(self, media_id: str) -> Dict:
        """Get engagement metrics for a post"""
        # Call MCP tool: get_media_insights
        pass
    
    async def get_recent_posts(self, limit: int = 10) -> List[Dict]:
        """Get recent posts with engagement data"""
        # Call MCP tool: get_media_posts
        pass
    
    async def get_account_insights(self) -> Dict:
        """Get account-level analytics"""
        # Call MCP tool: get_account_insights
        pass
```

---

## Updated Posting Methods

With MCP integration, Hungry Panda now supports 3 posting methods:

| Method | How it Works | Account Type | Automation Level |
|--------|--------------|--------------|------------------|
| **manual** | Agent prepares, you post via app | Any | Manual |
| **mcp** | Uses ig-mcp server via Graph API | Business/Creator | Automated |
| **browser** | Browser automation (legacy) | Any | Automated (risky) |

---

## Comparison: MCP vs Direct Integration

| Feature | Direct API | MCP (ig-mcp) |
|---------|-----------|--------------|
| Setup complexity | High | Medium (via MCP) |
| Code maintenance | All in-house | Shared (community) |
| Rate limiting | Manual | Built-in |
| Error handling | Custom | Standardized |
| Multi-client support | No | Yes (Claude, Cursor, etc.) |
| Updates | Manual | Via MCP server updates |

---

## Recommended Setup for Your Use Case

### If using Personal Instagram Account:
1. Use Hungry Panda in `manual` mode
2. The agent prepares content, you post via Instagram app
3. MCP not needed (no official API access anyway)

### If using Business/Creator Account:
1. Set up `ig-mcp` server with proper credentials
2. Configure Hungry Panda with MCP integration
3. Set `POSTING_METHOD=mcp`
4. Enjoy automated posting via official API

### If you need DMs + Posts:
1. Set up `ig-mcp` for posting (official API)
2. Optionally add `instagram_dm_mcp` for DMs (private API)
3. Use both MCP servers for different features

---

## Security Considerations

1. **Token Storage**
   - Store Instagram access tokens in `.env` only
   - Never commit credentials
   - Rotate tokens every 60 days

2. **API Limits**
   - ig-mcp has built-in rate limiting
   - 200 calls/hour for most endpoints
   - 25 posts/day limit

3. **Account Safety**
   - Use official Graph API (ig-mcp) when possible
   - Private API methods (DM MCP) have higher ban risk
   - Monitor for unusual activity

---

## Troubleshooting

### "Invalid access token"
- Token expired (valid 60 days)
- Missing required permissions
- Account not properly linked to Facebook Page

### "Rate limit exceeded"
- Built-in rate limiting in ig-mcp
- Wait for reset (hourly)
- Check rate limit headers

### "Media upload failed"
- Image format not supported
- File too large
- Aspect ratio issues

---

## Future Enhancements

1. **Convert Hungry Panda to MCP Server**
   - Allow Claude/Cursor to use Hungry Panda tools
   - Expose: `generate_strategy`, `analyze_content`, `track_competitor`

2. **Multi-MCP Support**
   - Use ig-mcp for posting
   - Use instagram_dm_mcp for DMs
   - Use meta-ads-mcp for advertising

3. **MCP Prompts**
   - Add MCP prompts for content strategy
   - Pre-built prompts for hashtag analysis
   - Engagement analysis templates

---

## Resources

- **ig-mcp:** https://github.com/jlbadano/ig-mcp
- **instagram_dm_mcp:** https://github.com/trypeggy/instagram_dm_mcp
- **meta-ads-mcp:** https://github.com/pipeboard-co/meta-ads-mcp
- **MCP Protocol:** https://modelcontextprotocol.io/
- **Instagram Graph API:** https://developers.facebook.com/docs/instagram-api/

---

## Summary

**MCP is the future** of AI integrations. By using `ig-mcp` with Hungry Panda:
- ✅ Official Instagram API access
- ✅ Standardized protocol
- ✅ Works with multiple AI clients
- ✅ Community-maintained
- ✅ Production-ready

**Recommendation:**
1. Keep Hungry Panda as your strategy/content engine
2. Add `ig-mcp` for Instagram API operations (if Business account)
3. Use MCP protocol for clean integration
4. Future-proof your architecture
