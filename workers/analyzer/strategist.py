"""
Strategist Engine
Generates weekly content strategies based on analysis
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List
import random

from infra.config.settings import config
from workers.analyzer.competitor_tracker import get_market_insights

# Weekly content themes that rotate
CONTENT_THEMES = [
    {
        "name": "Comfort Food Week",
        "focus": "Warm, nostalgic recipes that drive saves",
        "content_types": ["soups", "casseroles", "baked pasta", "hearty stews"],
        "hashtag_sets": ["#comfortfood", "#cozyvibes", "#soupsZN", "#homemade"],
        "expected_engagement": "high_saves"
    },
    {
        "name": "Quick & Easy Week",
        "focus": "30-minute meals for busy weeknights",
        "content_types": ["sheet pan dinners", "one-pot meals", "stir-fries", "quick pasta"],
        "hashtag_sets": ["#30minutemeals", "#quickdinner", "#weeknight", "#easymeals"],
        "expected_engagement": "high_shares"
    },
    {
        "name": "Global Flavors Week",
        "focus": "International cuisines to expand reach",
        "content_types": ["asian stir-fry", "mediterranean bowls", "mexican street food", "italian classics"],
        "hashtag_sets": ["#globalcuisine", "#internationalfood", "#ethnicfood", "#worldfood"],
        "expected_engagement": "high_reach"
    },
    {
        "name": "Meal Prep Week",
        "focus": "Batch cooking and prep ahead content",
        "content_types": ["lunch boxes", "prep bowls", "freezer meals", "healthy containers"],
        "hashtag_sets": ["#mealprep", "#lunchideas", "#healthymeals", "#prepahead"],
        "expected_engagement": "high_saves"
    },
    {
        "name": "Weekend Special Week",
        "focus": "Brunch and entertaining content",
        "content_types": ["brunch spreads", "pancakes & waffles", "party appetizers", "baked goods"],
        "hashtag_sets": ["#brunch", "#weekendvibes", "#breakfastgoals", "#sundayfunday"],
        "expected_engagement": "high_likes"
    }
]

# Optimal posting schedule based on engagement analysis
WEEKLY_SCHEDULE = {
    "monday": {"time": "18:00", "type": "dinner", "strategy": "Motivation Monday - start week strong"},
    "tuesday": {"time": "12:00", "type": "lunch", "strategy": "Tutorial Tuesday - teach a technique"},
    "wednesday": {"time": "18:00", "type": "dinner", "strategy": "Quick Wins - 30-min recipes"},
    "thursday": {"time": "08:00", "type": "breakfast", "strategy": "Throwback - classic recipe remake"},
    "friday": {"time": "17:00", "type": "dinner", "strategy": "Friday Feels - indulgent comfort"},
    "saturday": {"time": "10:00", "type": "brunch", "strategy": "Weekend Vibes - leisurely cooking"},
    "sunday": {"time": "17:00", "type": "prep", "strategy": "Sunday Prep - meal prep content"}
}


class Strategist:
    """Generates data-driven content strategies"""
    
    def __init__(self):
        self.conn = sqlite3.connect(config.DATABASE_PATH)
    
    def analyze_current_performance(self) -> Dict:
        """
        Analyze your own account performance to inform strategy
        """
        c = self.conn.cursor()
        
        # Get last 30 days of metrics
        c.execute("""
            SELECT * FROM growth_metrics 
            WHERE date >= date('now', '-30 days')
            ORDER BY date
        """)
        metrics = c.fetchall()
        
        # Get top performing posts
        c.execute("""
            SELECT * FROM content 
            WHERE status = 'posted' 
            ORDER BY engagement_score DESC 
            LIMIT 10
        """)
        top_posts = c.fetchall()
        
        # Analyze what's working
        if not metrics:
            return {
                "status": "insufficient_data",
                "message": "Need at least 2 weeks of posting to analyze patterns",
                "recommendation": "Start with 'Quick & Easy Week' theme - universally appealing"
            }
        
        # Calculate growth trajectory
        recent_followers = metrics[-1][2] if metrics else 0
        old_followers = metrics[0][2] if len(metrics) > 1 else recent_followers
        growth_rate = ((recent_followers - old_followers) / max(old_followers, 1)) * 100
        
        return {
            "growth_rate_30d": round(growth_rate, 2),
            "current_followers": recent_followers,
            "avg_engagement": sum(m[4] for m in metrics) / len(metrics) if metrics else 0,
            "top_performing_content": [p[2] for p in top_posts[:3]],  # filenames
            "momentum": "growing" if growth_rate > 5 else "stable" if growth_rate > 0 else "declining"
        }
    
    def select_weekly_theme(self, performance: Dict, competitor_insights: Dict) -> Dict:
        """
        Select the best theme for this week based on data
        """
        # If no data, start with safe choice
        if performance.get("status") == "insufficient_data":
            return CONTENT_THEMES[1]  # Quick & Easy Week
        
        # Consider momentum
        momentum = performance.get("momentum", "stable")
        
        # Consider competitor trends
        trending_patterns = competitor_insights.get("trending_content_patterns", [])
        
        # Score each theme based on fit
        theme_scores = []
        for theme in CONTENT_THEMES:
            score = 0
            
            # Boost if theme matches momentum need
            if momentum == "declining" and theme["expected_engagement"] == "high_saves":
                score += 3  # Saves help algorithm
            
            # Boost if matches competitor trends
            for pattern in trending_patterns:
                if any(pattern["pattern"].lower() in ct.lower() for ct in theme["content_types"]):
                    score += 2
            
            # Boost Quick & Easy for new accounts
            if performance.get("current_followers", 0) < 10000 and theme["name"] == "Quick & Easy Week":
                score += 2
            
            theme_scores.append((theme, score))
        
        # Select highest scoring theme
        selected = max(theme_scores, key=lambda x: x[1])[0]
        return selected
    
    def build_weekly_calendar(self, theme: Dict) -> List[Dict]:
        """
        Build a 7-day content calendar for the theme
        """
        calendar = []
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        content_pool = theme["content_types"].copy()
        
        for i, day in enumerate(days):
            schedule = WEEKLY_SCHEDULE[day]
            
            # Assign content type (cycle through available)
            content_type = content_pool[i % len(content_pool)]
            
            calendar.append({
                "day": day.title(),
                "posting_time": schedule["time"],
                "content_type": content_type,
                "content_format": "Reel" if i % 2 == 0 else "Carousel",  # Alternate formats
                "strategy": schedule["strategy"],
                "hashtags_to_use": theme["hashtag_sets"][:3] + ["#foodie", "#homecooking"]
            })
        
        return calendar
    
    def generate_hashtag_strategy(self, theme: Dict, competitor_insights: Dict) -> Dict:
        """
        Create a hashtag strategy for the week
        """
        # Get top hashtags from competitors
        competitor_tags = [h["tag"] for h in competitor_insights.get("top_performing_hashtags", [])[:5]]
        
        # Mix with theme tags
        primary_tags = theme["hashtag_sets"][:5]
        secondary_tags = competitor_tags[:5]
        
        # Add discovery tags
        discovery_tags = ["#foodporn", "#instafood", "#delicious", "#yummy", "#foodstagram"]
        
        return {
            "primary_hashtags": primary_tags,
            "secondary_hashtags": secondary_tags,
            "discovery_hashtags": discovery_tags,
            "branded_hashtags": ["#hungrypandacooks"],  # Can customize
            "usage_pattern": "Use 5-8 primary, 3-5 secondary, 2-3 discovery per post"
        }
    
    def create_growth_actions(self, performance: Dict, momentum: str) -> List[str]:
        """
        Generate specific growth actions for the week
        """
        actions = []
        
        if momentum == "declining":
            actions.extend([
                "Post 1 Reel daily for next 7 days (algorithm boost)",
                "Engage with 20 food accounts daily (community building)",
                "Add 'Save this recipe' CTA to every caption",
                "Test 2 new hashtag combinations"
            ])
        elif momentum == "stable":
            actions.extend([
                "Increase posting frequency from 5x to 7x weekly",
                "Create 1 'recipe card' carousel this week",
                "Respond to all comments within 2 hours",
                "Collaborate with 1 micro-influencer in food niche"
            ])
        else:  # growing
            actions.extend([
                "Double down on top performing content type",
                "Create a series: '3-part meal prep guide'",
                "Add recipe timestamps to video content",
                "Cross-post top Reel to Stories with engagement sticker"
            ])
        
        # Universal actions
        actions.extend([
            "Update bio with clear value proposition",
            "Create 3 Story highlights with recipe categories",
            "Pin top 3 performing posts to profile"
        ])
        
        return actions


async def generate_weekly_strategy() -> Dict:
    """
    Main entry point: Generate complete weekly strategy
    """
    strategist = Strategist()
    
    # Gather data
    performance = strategist.analyze_current_performance()
    competitor_insights = get_market_insights()
    
    # Select theme
    theme = strategist.select_weekly_theme(performance, competitor_insights)
    
    # Build calendar
    calendar = strategist.build_weekly_calendar(theme)
    
    # Generate hashtag strategy
    hashtag_strategy = strategist.generate_hashtag_strategy(theme, competitor_insights)
    
    # Create growth actions
    momentum = performance.get("momentum", "stable")
    growth_actions = strategist.create_growth_actions(performance, momentum)
    
    # Compile competitor insights
    insights = []
    if competitor_insights.get("tracked_count", 0) > 0:
        insights.append(f"Market avg engagement: {competitor_insights.get('market_avg_engagement', 0)}%")
        insights.append(f"Top trending pattern: {competitor_insights.get('trending_content_patterns', [{}])[0].get('pattern', 'N/A')}")
    
    return {
        "theme": theme["name"],
        "theme_description": theme["focus"],
        "period": f"{datetime.now().strftime('%b %d')} - {(datetime.now() + timedelta(days=7)).strftime('%b %d')}",
        "current_momentum": momentum,
        "content_calendar": calendar,
        "hashtags": hashtag_strategy,
        "insights": insights + competitor_insights.get("recommendations", []),
        "growth_actions": growth_actions,
        "expected_outcomes": {
            "follower_growth": "5-10%" if momentum == "growing" else "3-5%",
            "engagement_boost": "Target 4%+ engagement rate",
            "content_saves": "Focus on high-save content (recipes, meal prep)"
        }
    }


if __name__ == "__main__":
    import asyncio
    
    async def test():
        strategy = await generate_weekly_strategy()
        print(json.dumps(strategy, indent=2))
    
    asyncio.run(test())
