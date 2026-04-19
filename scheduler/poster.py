"""
Scheduler & Auto-Poster
Handles scheduling and automated posting to Instagram
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncio

from config.settings import config

logger = logging.getLogger(__name__)

# Posting methods - can use Instagram API, browser automation, or MCP
POSTING_METHODS = {
    "api": "Instagram Basic Display API (limited features)",
    "browser": "Browser automation with Selenium/Playwright",
    "manual": "Notify user to post manually with prepared content",
    "mcp": "Model Context Protocol via official Instagram Graph API"
}


class ContentScheduler:
    """Schedules and executes content posting"""
    
    def __init__(self):
        self.conn = sqlite3.connect(config.DATABASE_PATH)
    
    def get_scheduled_posts(self) -> List[Dict]:
        """
        Get all posts scheduled for today or earlier
        """
        c = self.conn.cursor()
        c.execute("""
            SELECT * FROM content 
            WHERE status = 'scheduled' 
            AND scheduled_time <= datetime('now', '+1 hour')
            ORDER BY scheduled_time ASC
        """)
        
        columns = [desc[0] for desc in c.description]
        posts = []
        for row in c.fetchall():
            post = dict(zip(columns, row))
            post['hashtags'] = json.loads(post['hashtags']) if post['hashtags'] else []
            posts.append(post)
        
        return posts
    
    def get_upcoming_schedule(self, days: int = 7) -> List[Dict]:
        """
        Get all scheduled posts for the next N days
        """
        c = self.conn.cursor()
        c.execute("""
            SELECT * FROM content 
            WHERE status = 'scheduled'
            AND scheduled_time <= datetime('now', '+{} days')
            ORDER BY scheduled_time ASC
        """.format(days))
        
        columns = [desc[0] for desc in c.description]
        posts = []
        for row in c.fetchall():
            post = dict(zip(columns, row))
            posts.append(post)
        
        return posts
    
    def mark_as_posted(self, content_id: str, external_id: Optional[str] = None) -> bool:
        """
        Mark content as posted and record metadata
        """
        c = self.conn.cursor()
        c.execute("""
            UPDATE content 
            SET status = 'posted', 
                posted_time = ?,
                external_id = ?
            WHERE id = ?
        """, (datetime.now(), external_id, content_id))
        
        self.conn.commit()
        return c.rowcount > 0
    
    def update_engagement_metrics(self, content_id: str, metrics: Dict):
        """
        Update engagement metrics for a posted item
        """
        c = self.conn.cursor()
        
        # Calculate engagement score
        likes = metrics.get('likes', 0)
        comments = metrics.get('comments', 0)
        saves = metrics.get('saves', 0)
        
        # Weighted engagement score (saves are most valuable in food niche)
        engagement_score = (likes * 1 + comments * 2 + saves * 3) / 100
        
        c.execute("""
            UPDATE content 
            SET likes = ?, comments = ?, saves = ?, engagement_score = ?
            WHERE id = ?
        """, (likes, comments, saves, engagement_score, content_id))
        
        self.conn.commit()
    
    def get_optimal_posting_times(self) -> Dict[str, str]:
        """
        Get AI-recommended optimal posting times based on content type
        """
        return {
            "breakfast": "08:00",
            "lunch": "12:00",
            "dinner": "18:00",
            "dessert": "15:00",
            "weekend_brunch": "10:00",
            "weekend_dinner": "17:00"
        }
    
    def suggest_schedule_slot(self, content_type: str = "dinner") -> Dict:
        """
        Suggest the next available optimal posting slot
        """
        optimal_times = self.get_optimal_posting_times()
        suggested_time = optimal_times.get(content_type, "18:00")
        
        # Find next available slot
        now = datetime.now()
        suggested_datetime = now.replace(hour=int(suggested_time[:2]), 
                                          minute=int(suggested_time[3:]), 
                                          second=0, microsecond=0)
        
        if suggested_datetime < now:
            suggested_datetime += timedelta(days=1)
        
        # Check if slot is available
        c = self.conn.cursor()
        c.execute("""
            SELECT COUNT(*) FROM content 
            WHERE status = 'scheduled' 
            AND date(scheduled_time) = date(?)
        """, (suggested_datetime,))
        
        count = c.fetchone()[0]
        
        return {
            "suggested_time": suggested_datetime.isoformat(),
            "time_display": suggested_datetime.strftime("%A %I:%M %p"),
            "available": count < config.MAX_POSTS_PER_DAY,
            "existing_posts_that_day": count,
            "reasoning": f"Optimal time for {content_type} content based on engagement analysis"
        }


class InstagramPoster:
    """Handles the actual posting to Instagram"""
    
    def __init__(self, method: str = "manual"):
        self.method = method
    
    async def post_content(self, content: Dict) -> Dict:
        """
        Post content to Instagram
        Returns result with status and external post ID
        """
        if self.method == "manual":
            # Send notification to user with prepared content
            return await self._manual_post(content)
        elif self.method == "mcp":
            # Use MCP (Model Context Protocol) for official API access
            return await self._mcp_post(content)
        elif self.method == "api":
            # Use Instagram API (requires proper setup)
            return await self._api_post(content)
        else:
            # Browser automation placeholder
            return await self._browser_post(content)
    
    async def _manual_post(self, content: Dict) -> Dict:
        """
        Prepare content for manual posting and notify user
        """
        prepared_content = {
            "content_id": content['id'],
            "filepath": content['filepath'],
            "caption": content['caption'],
            "hashtags": content.get('hashtags', []),
            "prepared_caption": f"{content['caption']}\n\n{' '.join(['#' + tag for tag in content.get('hashtags', [])])}",
            "posting_time": content.get('scheduled_time'),
            "action_required": "Open Instagram app and post this content now",
            "status": "ready_to_post"
        }
        
        logger.info(f"[MANUAL] Content ready for posting: {content['id']}")
        
        # In production: Send notification via email, push, or dashboard alert
        return {
            "success": True,
            "method": "manual",
            "prepared_content": prepared_content,
            "message": "Content ready for manual posting"
        }
    
    async def _mcp_post(self, content: Dict) -> Dict:
        """
        Post using MCP (Model Context Protocol) via Instagram Graph API
        
        This uses the official Instagram API through an MCP server (ig-mcp).
        Benefits:
        - Official API (safe, no ban risk)
        - Full automation
        - Built-in rate limiting
        - Rich analytics
        """
        try:
            # Import MCP client (lazy import to avoid circular dependencies)
            from integrations.mcp_client import publish_content_via_mcp
            
            logger.info(f"[MCP] Publishing content via MCP: {content['id']}")
            
            # Prepare content data
            content_data = {
                'id': content['id'],
                'filepath': content['filepath'],
                'caption': content.get('caption', ''),
                'hashtags': content.get('hashtags', [])
            }
            
            # Publish via MCP
            result = await publish_content_via_mcp(content['id'], content_data)
            
            if result['success']:
                logger.info(f"[MCP] Successfully published: {content['id']}")
                return {
                    "success": True,
                    "method": "mcp",
                    "external_id": result.get('media_id'),
                    "permalink": result.get('permalink'),
                    "message": "Content published via Instagram Graph API (MCP)"
                }
            else:
                logger.error(f"[MCP] Publishing failed: {result.get('error')}")
                return {
                    "success": False,
                    "method": "mcp",
                    "error": result.get('error', 'Unknown MCP error'),
                    "fallback": "Consider switching to manual posting method"
                }
                
        except ImportError as e:
            logger.error(f"[MCP] MCP client not available: {e}")
            return {
                "success": False,
                "method": "mcp",
                "error": f"MCP integration not available: {e}",
                "next_steps": [
                    "Ensure integrations/mcp_client.py exists",
                    "Install MCP dependencies",
                    "Or switch POSTING_METHOD to manual"
                ]
            }
        except Exception as e:
            logger.exception(f"[MCP] Unexpected error: {e}")
            return {
                "success": False,
                "method": "mcp",
                "error": str(e)
            }
    
    async def _api_post(self, content: Dict) -> Dict:
        """
        Post using Instagram API (limited to certain account types)
        """
        # Note: Instagram Basic Display API has limitations
        # Instagram Graph API requires business/creator account
        
        logger.warning("[API] Direct API posting not fully implemented")
        
        return {
            "success": False,
            "method": "api",
            "error": "Direct API posting deprecated. Use MCP method instead.",
            "next_steps": [
                "Switch POSTING_METHOD to mcp in config",
                "Set up ig-mcp server",
                "Configure INSTAGRAM_ACCESS_TOKEN"
            ]
        }
    
    async def _browser_post(self, content: Dict) -> Dict:
        """
        Post using browser automation (Selenium/Playwright)
        """
        # Placeholder - requires additional setup
        logger.warning("[BROWSER] Browser automation not implemented")
        
        return {
            "success": False,
            "method": "browser",
            "error": "Browser automation requires setup with credentials and anti-detection measures",
            "note": "Consider using MCP method or manual mode for better reliability"
        }


class AutoScheduler:
    """Background task scheduler for automated posting"""
    
    def __init__(self):
        self.scheduler = ContentScheduler()
        self.poster = InstagramPoster(method=config.POSTING_METHOD)
        self.running = False
    
    async def run_scheduler_loop(self):
        """
        Main scheduler loop - checks for posts to publish
        """
        self.running = True
        
        logger.info(f"[SCHEDULER] Started with posting method: {config.POSTING_METHOD}")
        
        while self.running:
            try:
                # Get posts ready to be published
                posts = self.scheduler.get_scheduled_posts()
                
                for post in posts:
                    # Check if it's time to post
                    scheduled = datetime.fromisoformat(post['scheduled_time']) if post['scheduled_time'] else None
                    
                    if scheduled and scheduled <= datetime.now():
                        logger.info(f"[SCHEDULER] Posting content: {post['id']}")
                        
                        result = await self.poster.post_content(post)
                        
                        if result['success']:
                            self.scheduler.mark_as_posted(
                                post['id'], 
                                result.get('external_id')
                            )
                            logger.info(f"[SCHEDULER] Successfully posted: {post['id']}")
                        else:
                            logger.error(f"[SCHEDULER] Post failed: {result.get('error')}")
                
                # Check every minute
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.exception(f"[SCHEDULER ERROR] {e}")
                await asyncio.sleep(60)
    
    def stop(self):
        self.running = False
        logger.info("[SCHEDULER] Stopped")


# Public interface functions

def get_schedule(days: int = 7) -> List[Dict]:
    """Get upcoming posting schedule"""
    scheduler = ContentScheduler()
    return scheduler.get_upcoming_schedule(days)


def suggest_best_time(content_type: str = "dinner") -> Dict:
    """Get AI-suggested posting time"""
    scheduler = ContentScheduler()
    return scheduler.suggest_schedule_slot(content_type)


async def run_automated_scheduler():
    """Start the automated scheduler (run as background task)"""
    auto = AutoScheduler()
    await auto.run_scheduler_loop()


if __name__ == "__main__":
    # Test scheduler
    print("Upcoming schedule:")
    for post in get_schedule():
        print(f"  - {post['id']}: {post.get('scheduled_time')}")
    
    print("\nSuggested slot:")
    print(suggest_best_time("dinner"))
