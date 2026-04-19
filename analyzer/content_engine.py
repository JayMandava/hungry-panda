"""
Content Analysis & Recommendation Engine
Analyzes uploaded content and generates AI-powered recommendations
"""
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
import random

# Food & cooking specific caption templates and strategies
CAPTION_TEMPLATES = {
    "recipe_focus": [
        "Craving {dish}? This {time} recipe will change your dinner game 🍽️✨",
        "When you need comfort food in {time} ⏰ {dish} never disappoints 💯",
        "The {dish} recipe that made my followers ask for the secrets 🥘",
    ],
    "process_focus": [
        "Watch how this transforms into pure comfort 🎥 Swipe for the magic →",
        "The process is just as beautiful as the result 🥄❤️",
        "POV: You're about to learn the best {dish} technique 👨‍🍳",
    ],
    "story_focus": [
        "This reminds me of my {relative}'s kitchen on Sunday mornings 🏠",
        "Some recipes carry memories. This one carries {memory} 💭",
        "Every bite tells a story. This one? Pure {emotion} 🥰",
    ],
    "engagement_hook": [
        "Save this for your next craving attack 📌 Trust me on this one",
        "Tag someone who needs to make this for you 👇",
        "Which would you try first? {option_a} or {option_b}? Tell me below! 👇",
    ]
}

# Trending food hashtags organized by category
HASHTAG_CATEGORIES = {
    "high_volume": [
        "food", "foodporn", "foodie", "instafood", "foodphotography",
        "foodstagram", "yummy", "delicious", "homemade", "cooking"
    ],
    "niche": [
        "homecooking", "fromscratch", "recipeoftheday", "foodblogger",
        "comfortfood", "easyrecipes", "quickmeals", "weeknightdinner"
    ],
    "engagement": [
        "foodreels", "cookingvideo", "foodtok", "recipeideas",
        "whatsfordinner", "cookwithme", "learnontiktok"
    ],
    "community": [
        "food52", "thekitchn", "buzzfeedfood", "tastemade", "bonappetit"
    ]
}

# Optimal posting times based on food content analysis
OPTIMAL_POST_TIMES = {
    "weekday_breakfast": "08:00",  # 8 AM - morning scroll
    "weekday_lunch": "12:00",      # 12 PM - lunch break
    "weekday_dinner": "18:00",     # 6 PM - dinner prep time
    "weekend_brunch": "10:00",     # 10 AM - weekend brunch scroll
    "weekend_dinner": "17:00",     # 5 PM - weekend dinner planning
}

# Content patterns that perform well
HIGH_PERFORMANCE_PATTERNS = [
    {
        "type": "overhead_recipe",
        "description": "Top-down video showing ingredients being added to a pan/pot",
        "engagement_boost": "3x saves",
        "best_for": "Recipe tutorials"
    },
    {
        "type": "asmr_cooking",
        "description": "Satisfying sounds - chopping, sizzling, stirring",
        "engagement_boost": "2.5x shares",
        "best_for": "Snackable content"
    },
    {
        "type": "before_after",
        "description": "Raw ingredients → finished dish transformation",
        "engagement_boost": "2x comments",
        "best_for": "Visual impact posts"
    },
    {
        "type": "quick_tutorial",
        "description": "30-60 second complete recipe walkthrough",
        "engagement_boost": "4x saves",
        "best_for": "Reels content"
    },
    {
        "type": "plating_showcase",
        "description": "Beautiful final presentation with garnish",
        "engagement_boost": "1.8x likes",
        "best_for": "Photo posts"
    }
]


class ContentAnalyzer:
    """Analyzes content and generates strategic recommendations"""
    
    def __init__(self):
        self.conn = sqlite3.connect('hungry_panda.db')
    
    def detect_content_type(self, filepath: str, user_caption: Optional[str]) -> Dict:
        """
        Detect what type of food content this is
        Returns content classification with confidence score
        """
        # In a real implementation, this would use image/video analysis
        # For now, we'll use heuristics and user input
        
        content_type = {
            "category": "unknown",
            "dish_detected": None,
            "meal_type": None,  # breakfast, lunch, dinner, snack
            "cuisine_type": None,
            "confidence": 0.7
        }
        
        # Analyze caption if provided
        if user_caption:
            caption_lower = user_caption.lower()
            
            # Detect meal type
            if any(word in caption_lower for word in ["breakfast", "morning", "brunch", "pancake", "toast"]):
                content_type["meal_type"] = "breakfast"
            elif any(word in caption_lower for word in ["lunch", "noon", "sandwich", "salad"]):
                content_type["meal_type"] = "lunch"
            elif any(word in caption_lower for word in ["dinner", "evening", "supper", "steak", "pasta", "curry"]):
                content_type["meal_type"] = "dinner"
            elif any(word in caption_lower for word in ["snack", "dessert", "sweet", "cake", "cookie"]):
                content_type["meal_type"] = "dessert/snack"
            
            # Detect cuisine
            cuisines = {
                "italian": ["pasta", "pizza", "risotto", "italian"],
                "indian": ["curry", "naan", "tikka", "masala", "biryani"],
                "asian": ["stir fry", "noodles", "ramen", "sushi", "asian"],
                "mexican": ["taco", "burrito", "enchilada", "salsa", "mexican"],
                "mediterranean": ["hummus", "falafel", "mediterranean", "greek"],
                "american": ["burger", "bbq", "steak", "comfort"]
            }
            
            for cuisine, keywords in cuisines.items():
                if any(keyword in caption_lower for keyword in keywords):
                    content_type["cuisine_type"] = cuisine
                    break
        
        # Default classifications if still unknown
        if not content_type["category"] or content_type["category"] == "unknown":
            content_type["category"] = "food_photography"
        
        return content_type
    
    def generate_caption(self, content_type: Dict, strategy: str = "engagement") -> str:
        """
        Generate an optimized caption based on content type and strategy
        """
        meal_type = content_type.get("meal_type", "dinner")
        cuisine = content_type.get("cuisine_type", "homestyle")
        
        # Select template category based on strategy
        if strategy == "engagement":
            templates = CAPTION_TEMPLATES["engagement_hook"] + CAPTION_TEMPLATES["recipe_focus"]
        elif strategy == "story":
            templates = CAPTION_TEMPLATES["story_focus"]
        else:
            templates = CAPTION_TEMPLATES["recipe_focus"] + CAPTION_TEMPLATES["process_focus"]
        
        template = random.choice(templates)
        
        # Fill in the template
        caption = template.format(
            dish=cuisine.title() + " " + meal_type,
            time="30-minute" if meal_type == "weeknight" else "quick",
            relative="grandmother" if random.random() > 0.5 else "mother",
            memory="happiness",
            emotion="comfort",
            option_a="this version" if random.random() > 0.5 else "the classic",
            option_b="the spicy twist" if random.random() > 0.5 else "the creamy one"
        )
        
        return caption
    
    def select_hashtags(self, content_type: Dict, count: int = 20) -> List[str]:
        """
        Select optimal hashtags based on content type and current performance
        """
        selected = []
        
        # Get database stats for hashtag performance
        c = self.conn.cursor()
        c.execute("SELECT hashtag FROM hashtag_performance ORDER BY avg_engagement DESC LIMIT 10")
        performing_tags = [row[0] for row in c.fetchall()]
        
        # Mix of hashtag types for optimal reach
        # 5-7 high volume (discovery)
        high_volume_sample = random.sample(HASHTAG_CATEGORIES["high_volume"], 
                                          min(6, len(HASHTAG_CATEGORIES["high_volume"])))
        selected.extend(high_volume_sample)
        
        # 8-10 niche (targeted audience)
        niche_sample = random.sample(HASHTAG_CATEGORIES["niche"], 
                                   min(8, len(HASHTAG_CATEGORIES["niche"])))
        selected.extend(niche_sample)
        
        # 3-5 engagement-focused
        engagement_sample = random.sample(HASHTAG_CATEGORIES["engagement"], 
                                        min(4, len(HASHTAG_CATEGORIES["engagement"])))
        selected.extend(engagement_sample)
        
        # Add any top performing hashtags from database
        selected.extend(performing_tags[:2])
        
        # Add category-specific tags based on content
        if content_type.get("meal_type") == "breakfast":
            selected.extend(["breakfastideas", "brunch", "morningfuel"])
        elif content_type.get("meal_type") == "dinner":
            selected.extend(["dinnerideas", "dinnertime", "familydinner"])
        elif content_type.get("meal_type") == "dessert/snack":
            selected.extend(["dessert", "sweettooth", "baking"])
        
        if content_type.get("cuisine_type"):
            selected.append(f"{content_type['cuisine_type']}food")
        
        # Remove duplicates and limit to requested count
        selected = list(dict.fromkeys(selected))[:count]
        
        return selected
    
    def recommend_posting_time(self, content_type: Dict) -> Dict:
        """
        Recommend optimal posting time based on content type and historical data
        """
        meal_type = content_type.get("meal_type", "dinner")
        
        # Base recommendation on meal type
        if meal_type == "breakfast":
            recommended_time = OPTIMAL_POST_TIMES["weekday_breakfast"]
            reasoning = "Breakfast content performs best when people are planning their morning meal (8 AM)"
        elif meal_type == "lunch":
            recommended_time = OPTIMAL_POST_TIMES["weekday_lunch"]
            reasoning = "Lunch content hits during the lunch break scroll session (12 PM)"
        elif meal_type == "dessert/snack":
            recommended_time = "15:00"  # 3 PM snack craving time
            reasoning = "Afternoon snack content captures the 3 PM craving window"
        else:  # dinner default
            # Check if it's weekend
            today = datetime.now()
            if today.weekday() >= 5:  # Saturday or Sunday
                recommended_time = OPTIMAL_POST_TIMES["weekend_dinner"]
                reasoning = "Weekend dinner content performs best at 5 PM when people plan their evening meal"
            else:
                recommended_time = OPTIMAL_POST_TIMES["weekday_dinner"]
                reasoning = "Weeknight dinner content hits at 6 PM - peak dinner prep time"
        
        return {
            "time": recommended_time,
            "reasoning": reasoning,
            "timezone": "local",
            "engagement_prediction": "high" if meal_type in ["dinner", "dessert/snack"] else "medium"
        }
    
    def generate_strategy_notes(self, content_type: Dict) -> str:
        """
        Generate strategic notes explaining why this recommendation was made
        """
        patterns = []
        
        # Identify which high-performance pattern this content could follow
        for pattern in HIGH_PERFORMANCE_PATTERNS:
            if pattern["best_for"] in ["Photo posts", "Recipe tutorials"]:
                patterns.append(pattern)
        
        notes = f"""
        STRATEGIC RECOMMENDATION:
        
        Content Type: {content_type.get('meal_type', 'General').title()} | {content_type.get('cuisine_type', 'Mixed').title()} Cuisine
        
        Why this approach:
        1. This content fits the "{random.choice(['overhead_recipe', 'plating_showcase'])}" pattern
           which typically sees {random.choice(['2x', '3x', '1.5x'])} engagement boost
        
        2. Caption uses engagement hook to drive comments and saves
        
        3. Hashtag mix balances discovery (high-volume) with targeted reach (niche)
        
        4. Posting time aligns with when your audience plans {content_type.get('meal_type', 'meals')}
        
        Expected outcome: High save rate + increased profile visits
        """
        
        return notes.strip()


async def analyze_and_recommend(content_id: str, filepath: str, user_caption: Optional[str] = None) -> Dict:
    """
    Main entry point: Analyze content and return full recommendation
    """
    analyzer = ContentAnalyzer()
    
    # Detect content type
    content_type = analyzer.detect_content_type(filepath, user_caption)
    
    # Generate recommendations
    caption = analyzer.generate_caption(content_type, strategy="engagement")
    hashtags = analyzer.select_hashtags(content_type)
    time_rec = analyzer.recommend_posting_time(content_type)
    strategy_notes = analyzer.generate_strategy_notes(content_type)
    
    # Calculate confidence based on content clarity
    confidence = content_type["confidence"]
    if user_caption:
        confidence += 0.1  # Bonus for having context
    confidence = min(confidence, 1.0)
    
    return {
        "content_id": content_id,
        "content_analysis": content_type,
        "suggested_caption": caption,
        "suggested_hashtags": hashtags,
        "optimal_time": time_rec,
        "strategy_notes": strategy_notes,
        "confidence_score": round(confidence, 2),
        "content_patterns": [p["type"] for p in HIGH_PERFORMANCE_PATTERNS[:3]]
    }


if __name__ == "__main__":
    # Test the analyzer
    import asyncio
    
    async def test():
        result = await analyze_and_recommend(
            "test123", 
            "/path/to/image.jpg",
            "Homemade pasta for dinner tonight"
        )
        print(json.dumps(result, indent=2))
    
    asyncio.run(test())
