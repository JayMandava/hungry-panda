"""
Competitor Tracking & Analysis
Monitors competitor accounts to extract insights and patterns
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from infra.config.settings import config

# Simulated competitor analysis - in production, this would use:
# - Instagram API
# - Web scraping
# - Third-party social listening tools

# Mock database of successful food accounts for analysis
SAMPLE_COMPETITORS = {
    "halfbakedharvest": {
        "followers": 2500000,
        "content_style": "rustic comfort food, overhead shots, warm tones",
        "posting_frequency": "daily",
        "top_performing": ["pasta recipes", "cozy soups", "holiday baking"],
        "avg_engagement_rate": 4.2,
        "hashtag_strategy": "branded hashtags + niche community tags",
        "caption_style": "story-driven, personal anecdotes"
    },
    "minimalistbaker": {
        "followers": 1800000,
        "content_style": "minimalist, 10 ingredients or less, quick recipes",
        "posting_frequency": "5x/week",
        "top_performing": ["30-min meals", "plant-based", "one-pot"],
        "avg_engagement_rate": 3.8,
        "hashtag_strategy": "#minimalistbaker branded + #vegan #quickrecipes",
        "caption_style": "direct, helpful, recipe-focused"
    },
    "buzzfeedtasty": {
        "followers": 35000000,
        "content_style": "fast-paced overhead, text overlays, satisfying cuts",
        "posting_frequency": "multiple daily",
        "top_performing": ["cheese pulls", "quick hacks", "viral trends"],
        "avg_engagement_rate": 2.1,
        "hashtag_strategy": "high-volume trending hashtags",
        "caption_style": "hooks, questions, engagement triggers"
    },
    "damn_delicious": {
        "followers": 900000,
        "content_style": "clean food photography, weeknight focus, family meals",
        "posting_frequency": "daily",
        "top_performing": ["sheet pan dinners", "30-min meals", "meal prep"],
        "avg_engagement_rate": 3.5,
        "hashtag_strategy": "#weeknightdinner #easymeals #familydinner",
        "caption_style": "relatable, busy parent tone"
    }
}

INDUSTRY_TRENDING_HASHTAGS = [
    {"hashtag": "foodandbeverage", "category": "f&b", "avg_engagement": 4.8},
    {"hashtag": "restaurantlife", "category": "restaurant", "avg_engagement": 4.6},
    {"hashtag": "chefstable", "category": "restaurant", "avg_engagement": 4.5},
    {"hashtag": "hospitalitylife", "category": "hotel", "avg_engagement": 4.3},
    {"hashtag": "hotelrestaurant", "category": "hotel", "avg_engagement": 4.2},
    {"hashtag": "finedining", "category": "restaurant", "avg_engagement": 4.7},
    {"hashtag": "brunchgoals", "category": "restaurant", "avg_engagement": 4.1},
    {"hashtag": "cocktailculture", "category": "beverage", "avg_engagement": 4.0},
    {"hashtag": "cafevibes", "category": "cafe", "avg_engagement": 4.1},
    {"hashtag": "foodpresentation", "category": "f&b", "avg_engagement": 4.4},
    {"hashtag": "luxurydining", "category": "hotel", "avg_engagement": 3.9},
    {"hashtag": "restaurantmarketing", "category": "business", "avg_engagement": 3.8},
]


class CompetitorTracker:
    """Tracks and analyzes competitor Instagram accounts"""
    
    def __init__(self):
        self.conn = sqlite3.connect(config.DATABASE_PATH)
    
    async def analyze_account(self, username: str) -> Dict:
        """
        Analyze a competitor account and extract insights
        """
        # In production: Use Instagram API or scraping
        # For demo: Use sample data or simulate analysis
        
        if username.lower() in SAMPLE_COMPETITORS:
            data = SAMPLE_COMPETITORS[username.lower()]
            return {
                "username": username,
                "followers": data["followers"],
                "avg_engagement": data["avg_engagement_rate"],
                "content_style": data["content_style"],
                "top_hashtags": self._extract_hashtags(data["hashtag_strategy"]),
                "patterns": data["top_performing"],
                "posting_frequency": data["posting_frequency"],
                "caption_approach": data["caption_style"]
            }
        
        # Simulate analysis for unknown accounts
        return {
            "username": username,
            "followers": "unknown - requires API access",
            "avg_engagement": "unknown - requires monitoring",
            "content_style": "analysis pending",
            "top_hashtags": [],
            "patterns": [],
            "note": "Connect Instagram API for live competitor tracking"
        }
    
    def _extract_hashtags(self, hashtag_text: str) -> List[str]:
        """Extract hashtags from strategy text"""
        # Simple extraction - in production, would analyze actual posts
        common_hashtags = [
            "foodporn", "foodie", "instafood", "recipe", "homecooking",
            "foodstagram", "delicious", "yummy", "cooking", "chef"
        ]
        return common_hashtags[:5]
    
    def get_competitor_insights(self) -> Dict:
        """
        Aggregate insights from all tracked competitors
        """
        c = self.conn.cursor()
        c.execute("SELECT * FROM competitors ORDER BY avg_engagement DESC")
        competitors = c.fetchall()
        
        if not competitors:
            return {
                "status": "no_competitors",
                "message": "Add competitors to track to see insights"
            }
        
        # Analyze patterns across competitors
        all_hashtags = []
        all_patterns = []
        total_engagement = 0
        
        for comp in competitors:
            hashtags = json.loads(comp[5]) if comp[5] else []
            patterns = json.loads(comp[6]) if comp[6] else []
            all_hashtags.extend(hashtags)
            all_patterns.extend(patterns)
            total_engagement += comp[3] or 0
        
        # Find most common hashtags
        from collections import Counter
        hashtag_counts = Counter(all_hashtags)
        top_hashtags = hashtag_counts.most_common(10)
        
        # Identify trending patterns
        pattern_counts = Counter(all_patterns)
        top_patterns = pattern_counts.most_common(5)
        
        avg_engagement = total_engagement / len(competitors) if competitors else 0
        
        return {
            "tracked_count": len(competitors),
            "market_avg_engagement": round(avg_engagement, 2),
            "top_performing_hashtags": [{"tag": tag, "count": count} for tag, count in top_hashtags],
            "trending_content_patterns": [{"pattern": pat, "mentions": count} for pat, count in top_patterns],
            "recommendations": self._generate_competitor_recommendations(top_patterns, top_hashtags)
        }
    
    def _generate_competitor_recommendations(self, patterns, hashtags) -> List[str]:
        """Generate actionable recommendations based on competitor analysis"""
        recommendations = []
        
        if patterns:
            top_pattern = patterns[0][0]
            recommendations.append(
                f"Top competitors are posting {top_pattern} content. Consider creating similar content this week."
            )
        
        if hashtags:
            top_tag = hashtags[0][0]
            recommendations.append(
                f"#{top_tag} is trending across competitors. Add it to your next 3 posts."
            )
        
        recommendations.extend([
            "Competitors posting at 6 PM see highest engagement. Align your schedule.",
            "Video content (Reels) showing the cooking process outperforms static posts by 2x",
            "Captions with recipe yield/time info get more saves - add these details"
        ])
        
        return recommendations


async def analyze_competitor(username: str) -> Dict:
    """Public interface for competitor analysis"""
    tracker = CompetitorTracker()
    return await tracker.analyze_account(username)


def get_market_insights() -> Dict:
    """Get aggregated insights from all tracked competitors"""
    tracker = CompetitorTracker()
    return tracker.get_competitor_insights()


def get_industry_trending_hashtags(limit: int = 10) -> List[Dict]:
    """Return fallback trending hashtags tailored to F&B, restaurants, and hotels."""
    return INDUSTRY_TRENDING_HASHTAGS[:limit]


if __name__ == "__main__":
    import asyncio
    
    async def test():
        result = await analyze_competitor("halfbakedharvest")
        print(json.dumps(result, indent=2))
    
    asyncio.run(test())
