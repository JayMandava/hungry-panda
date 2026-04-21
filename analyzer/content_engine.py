"""
Content Analysis & Recommendation Engine
Analyzes uploaded content and generates AI-powered recommendations
"""
import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
import random

# Optional LLM integration
try:
    from integrations.llm_client import (
        analyze_visual_asset as llm_analyze_visual_asset,
        generate_caption as llm_generate_caption,
        generate_hashtags as llm_generate_hashtags,
    )
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

logger = logging.getLogger(__name__)

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

MEAL_KEYWORDS = {
    "breakfast": ["breakfast", "morning", "toast", "omelette", "omelet", "pancake", "waffle", "granola"],
    "brunch": ["brunch", "dosa", "idli", "upma", "avocado toast", "shakshuka"],
    "lunch": ["lunch", "salad", "sandwich", "bowl", "wrap", "burger", "rice bowl"],
    "dinner": ["dinner", "supper", "pizza", "pasta", "curry", "biryani", "steak", "ramen", "tacos"],
    "dessert/snack": ["dessert", "snack", "cake", "cookie", "brownie", "ice cream", "pastry", "fries"],
    "beverage": ["coffee", "latte", "espresso", "tea", "smoothie", "juice", "cocktail", "mocktail"],
}

CUISINE_KEYWORDS = {
    "italian": ["pizza", "pasta", "risotto", "lasagna", "italian"],
    "indian": ["dosa", "idli", "sambar", "curry", "naan", "tikka", "masala", "biryani", "paneer"],
    "asian": ["ramen", "sushi", "noodles", "dumpling", "stir fry", "bao", "asian"],
    "mexican": ["taco", "quesadilla", "burrito", "enchilada", "mexican"],
    "american": ["burger", "bbq", "wings", "fries", "american"],
    "mediterranean": ["falafel", "hummus", "shawarma", "greek", "mediterranean"],
}

DISH_KEYWORDS = [
    "dosa",
    "pizza",
    "pasta",
    "curry",
    "biryani",
    "burger",
    "ramen",
    "salad",
    "sandwich",
    "taco",
    "coffee",
    "latte",
    "smoothie",
    "cake",
    "cookie",
]


class ContentAnalyzer:
    """Analyzes content and generates strategic recommendations"""
    
    def __init__(self):
        self.conn = sqlite3.connect('hungry_panda.db')

    def _get_rng(self, seed: str) -> random.Random:
        """Return a deterministic RNG for stable but content-specific variants."""
        return random.Random(seed)

    def merge_visual_analysis(self, content_type: Dict, visual_analysis: Optional[Dict]) -> Dict:
        """Merge compact vision facts into the detected content type."""
        if not visual_analysis:
            return content_type

        merged = dict(content_type)
        if visual_analysis.get("dish_detected"):
            merged["dish_detected"] = visual_analysis["dish_detected"]
        if visual_analysis.get("meal_type") and visual_analysis.get("meal_type") != "unknown":
            merged["meal_type"] = visual_analysis["meal_type"]
        if visual_analysis.get("cuisine_type"):
            merged["cuisine_type"] = visual_analysis["cuisine_type"]
        if visual_analysis.get("format"):
            merged["format"] = visual_analysis["format"]
        if visual_analysis.get("confidence") is not None:
            merged["confidence"] = max(float(merged.get("confidence", 0.5)), float(visual_analysis["confidence"]))
        return merged

    def infer_content_signals(self, text: str) -> Dict[str, Optional[str]]:
        """Infer meal type and cuisine from any available text context."""
        lower_text = (text or "").lower()
        result: Dict[str, Optional[str]] = {"meal_type": None, "cuisine_type": None, "dish_detected": None}

        for meal_type, keywords in MEAL_KEYWORDS.items():
            if any(keyword in lower_text for keyword in keywords):
                result["meal_type"] = meal_type
                break

        for cuisine, keywords in CUISINE_KEYWORDS.items():
            if any(keyword in lower_text for keyword in keywords):
                result["cuisine_type"] = cuisine
                break

        for dish in DISH_KEYWORDS:
            if dish in lower_text:
                result["dish_detected"] = dish
                break

        return result

    def build_visual_description(
        self,
        visual_analysis: Optional[Dict],
        user_caption: Optional[str],
        context: Optional[str],
    ) -> str:
        """Build a grounded content description that prioritizes what the image actually shows."""
        parts: List[str] = []
        if visual_analysis:
            if visual_analysis.get("dish_detected"):
                parts.append(f"Visible dish: {visual_analysis['dish_detected']}")
            if visual_analysis.get("visual_summary"):
                parts.append(f"Visual summary: {visual_analysis['visual_summary']}")
            if visual_analysis.get("meal_type") and visual_analysis.get("meal_type") != "unknown":
                parts.append(f"Meal type: {visual_analysis['meal_type']}")
            if visual_analysis.get("cuisine_type"):
                parts.append(f"Cuisine: {visual_analysis['cuisine_type']}")
            if visual_analysis.get("contradicts_user_text"):
                parts.append("The uploaded image conflicts with the provided text context.")
        if context:
            parts.append(f"User context: {context}")
        if user_caption:
            parts.append(f"User caption: {user_caption}")
        return " | ".join(parts).strip()

    def build_non_food_response(
        self,
        content_id: str,
        content_type: Dict,
        visual_analysis: Dict,
    ) -> Dict:
        """Return a safe response when the uploaded asset does not appear to contain food content."""
        summary = visual_analysis.get("visual_summary") or visual_analysis.get("primary_subject") or "The uploaded asset does not appear to show food."
        mismatch = visual_analysis.get("contradicts_user_text")
        mismatch_note = " The image appears to conflict with the text you entered." if mismatch else ""
        note = (
            f"This upload looks like non-food content: {summary}.{mismatch_note} "
            "Growth recommendations for food content would be guesswork until the visual matches the concept."
        )
        return {
            "content_id": content_id,
            "content_analysis": content_type,
            "suggested_caption": "This upload does not appear to show food or hospitality content. Upload a food asset to get growth-ready recommendations.",
            "suggested_hashtags": [],
            "caption_variants": [
                {
                    "label": "Needs Matching Asset",
                    "caption": "This upload does not appear to show food or hospitality content. Upload a relevant asset to generate growth-ready caption ideas.",
                    "why": "Avoid publishing a misleading caption against a mismatched asset.",
                },
                {
                    "label": "Use Correct Visual First",
                    "caption": "The uploaded image conflicts with the described dish. Replace it with the actual food visual before optimizing for reach.",
                    "why": "Visual-content mismatch weakens trust, clicks, and conversion into follows.",
                },
            ],
            "hashtag_variants": [
                {
                    "label": "Not Recommended",
                    "hashtags": [],
                    "why": "Hashtags would be misleading until the visual matches the intended food post.",
                },
                {
                    "label": "Not Recommended",
                    "hashtags": [],
                    "why": "Upload the actual food image first, then build discovery and intent hashtags around it.",
                },
            ],
            "optimal_time": {
                "time": "N/A",
                "reasoning": "Posting-time optimization is intentionally withheld because the uploaded asset does not appear to be a food or hospitality post.",
                "timezone": "local",
                "engagement_prediction": "low",
            },
            "strategy_notes": note,
            "confidence_score": 0.18,
            "content_patterns": [],
            "thinking_sections": [
                {"title": "Content Read", "content": summary},
                {"title": "Timing Logic", "content": "No timing recommendation was produced because the visual is not a usable food post."},
                {"title": "Strategy Notes", "content": note},
                {"title": "Confidence Breakdown", "content": "Confidence is intentionally low because the uploaded image does not align with the requested food recommendation."},
            ],
        }

    def normalize_llm_recommendation(
        self,
        content_id: str,
        filepath: str,
        user_caption: Optional[str],
        context: Optional[str],
        llm_result: Dict,
    ) -> Dict:
        """Normalize a structured LLM response into the UI contract used by the app."""
        description = context or user_caption or ""
        seed = f"{content_id}:{filepath}:{user_caption or ''}:{context or ''}"
        fallback_content_type = self.detect_content_type(filepath, user_caption)
        fallback_time = self.recommend_posting_time(fallback_content_type, description)
        fallback_notes = self.generate_strategy_notes(fallback_content_type, description, seed)

        content_type = dict(fallback_content_type)
        content_type.update(llm_result.get("content_analysis") or {})
        if not content_type.get("format"):
            content_type["format"] = fallback_content_type.get("format", "image")

        caption_variants = self._normalize_caption_variants(
            llm_result.get("caption_variants"),
            content_type,
            description,
            seed,
        )
        hashtag_variants = self._normalize_hashtag_variants(
            llm_result.get("hashtag_variants"),
            content_type,
            description,
            seed,
        )

        optimal_time = llm_result.get("optimal_time") or fallback_time
        if not isinstance(optimal_time, dict):
            optimal_time = fallback_time

        strategy_notes = (llm_result.get("strategy_notes") or "").strip() or fallback_notes
        confidence = self._normalize_confidence(llm_result.get("confidence_score"), content_type, user_caption, context)
        thinking_sections = llm_result.get("thinking_sections") or self.build_thinking_sections(
            content_type,
            optimal_time,
            confidence,
            strategy_notes,
        )
        content_patterns = llm_result.get("content_patterns") or [p["type"] for p in HIGH_PERFORMANCE_PATTERNS[:3]]

        return {
            "content_id": content_id,
            "content_analysis": content_type,
            "suggested_caption": caption_variants[0]["caption"],
            "suggested_hashtags": hashtag_variants[0]["hashtags"],
            "caption_variants": caption_variants,
            "hashtag_variants": hashtag_variants,
            "optimal_time": {
                "time": optimal_time.get("time", fallback_time["time"]),
                "reasoning": optimal_time.get("reasoning", fallback_time["reasoning"]),
                "timezone": optimal_time.get("timezone", "local"),
                "engagement_prediction": optimal_time.get("engagement_prediction", fallback_time.get("engagement_prediction", "medium")),
            },
            "strategy_notes": strategy_notes,
            "confidence_score": round(confidence, 2),
            "content_patterns": content_patterns,
            "thinking_sections": thinking_sections,
        }

    def _normalize_caption_variants(
        self,
        raw_variants: Optional[List[Dict]],
        content_type: Dict,
        content_description: str,
        seed: str,
    ) -> List[Dict]:
        if not isinstance(raw_variants, list):
            return self.build_caption_variants(content_type, content_description, seed)

        normalized: List[Dict] = []
        fallback = self.build_caption_variants(content_type, content_description, seed)
        for index in range(2):
            source = raw_variants[index] if index < len(raw_variants) and isinstance(raw_variants[index], dict) else {}
            fallback_item = fallback[index]
            caption = str(source.get("caption") or fallback_item["caption"]).strip()
            normalized.append(
                {
                    "label": str(source.get("label") or fallback_item["label"]).strip(),
                    "caption": caption,
                    "why": str(source.get("why") or fallback_item["why"]).strip(),
                }
            )
        return normalized

    def _normalize_hashtag_variants(
        self,
        raw_variants: Optional[List[Dict]],
        content_type: Dict,
        content_description: str,
        seed: str,
    ) -> List[Dict]:
        if not isinstance(raw_variants, list):
            return self.build_hashtag_variants(content_type, content_description, seed)

        normalized: List[Dict] = []
        fallback = self.build_hashtag_variants(content_type, content_description, seed)
        for index in range(2):
            source = raw_variants[index] if index < len(raw_variants) and isinstance(raw_variants[index], dict) else {}
            fallback_item = fallback[index]
            raw_tags = source.get("hashtags")
            if not isinstance(raw_tags, list):
                raw_tags = fallback_item["hashtags"]
            tags = [str(tag).lstrip("#").strip() for tag in raw_tags if str(tag).strip()]
            if not tags:
                tags = fallback_item["hashtags"]
            normalized.append(
                {
                    "label": str(source.get("label") or fallback_item["label"]).strip(),
                    "hashtags": tags[:20],
                    "why": str(source.get("why") or fallback_item["why"]).strip(),
                }
            )
        return normalized

    def _normalize_confidence(
        self,
        raw_confidence: Optional[float],
        content_type: Dict,
        user_caption: Optional[str],
        context: Optional[str],
    ) -> float:
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            confidence = float(content_type.get("confidence") or 0.55)
            if user_caption:
                confidence += 0.08
            if context:
                confidence += 0.12
            if content_type.get("meal_type"):
                confidence += 0.05
            if content_type.get("cuisine_type"):
                confidence += 0.03
            if content_type.get("format") == "video":
                confidence += 0.02
        return max(0.1, min(confidence, 0.99))
    
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
            "format": "video" if filepath.lower().endswith((".mov", ".mp4", ".m4v", ".avi")) else "image",
            "confidence": 0.65
        }
        
        # Analyze caption if provided
        if user_caption:
            caption_lower = user_caption.lower()
            inferred = self.infer_content_signals(caption_lower)
            if inferred.get("meal_type"):
                content_type["meal_type"] = inferred["meal_type"]
            if inferred.get("cuisine_type"):
                content_type["cuisine_type"] = inferred["cuisine_type"]

            if any(word in caption_lower for word in ["reel", "video", "step by step", "watch", "pour", "sizzle"]):
                content_type["format"] = "video"
                content_type["confidence"] += 0.05

            if any(word in caption_lower for word in ["plate", "plated", "garnish", "served", "presentation"]):
                content_type["category"] = "food_photography"
                content_type["confidence"] += 0.05
        
        # Default classifications if still unknown
        if not content_type["category"] or content_type["category"] == "unknown":
            content_type["category"] = "recipe_tutorial" if content_type["format"] == "video" else "food_photography"

        if content_type.get("meal_type"):
            content_type["confidence"] += 0.08
        if content_type.get("cuisine_type"):
            content_type["confidence"] += 0.07
        content_type["confidence"] = min(content_type["confidence"], 0.9)
        
        return content_type

    def refine_content_type(
        self,
        filepath: str,
        user_caption: Optional[str],
        context: Optional[str],
        visual_analysis: Optional[Dict],
    ) -> Dict:
        """Combine heuristics, text context, and visual clues into one content-type view."""
        combined_text = " ".join(part for part in [user_caption or "", context or ""] if part).strip()
        content_type = self.detect_content_type(filepath, combined_text or None)
        inferred = self.infer_content_signals(combined_text)
        if inferred.get("meal_type") and not content_type.get("meal_type"):
            content_type["meal_type"] = inferred["meal_type"]
        if inferred.get("cuisine_type") and not content_type.get("cuisine_type"):
            content_type["cuisine_type"] = inferred["cuisine_type"]
        if inferred.get("dish_detected") and not content_type.get("dish_detected"):
            content_type["dish_detected"] = inferred["dish_detected"]
        return self.merge_visual_analysis(content_type, visual_analysis)
    
    def generate_caption(
        self,
        content_type: Dict,
        strategy: str = "engagement",
        content_description: str = "",
        rng: Optional[random.Random] = None,
    ) -> str:
        """
        Generate an optimized caption based on content type and strategy.
        Uses LLM if configured, otherwise falls back to templates.
        """
        rng = rng or random.Random()
        meal_type = content_type.get("meal_type", "dinner")
        cuisine = content_type.get("cuisine_type", "homestyle")
        dish_name = content_type.get("dish_detected") or f"{cuisine} {meal_type}".strip()
        
        # Try LLM first if available
        if LLM_AVAILABLE:
            try:
                description = content_description or f"{dish_name} food"
                return llm_generate_caption(
                    content_description=description,
                    content_type=meal_type,
                    cuisine=cuisine,
                    tone=strategy
                )
            except Exception as e:
                logger.warning(f"LLM caption generation failed, using templates: {e}")
        
        # Fall back to template-based generation
        # Select template category based on strategy
        if strategy == "engagement":
            templates = CAPTION_TEMPLATES["engagement_hook"] + CAPTION_TEMPLATES["recipe_focus"]
        elif strategy == "story":
            templates = CAPTION_TEMPLATES["story_focus"]
        else:
            templates = CAPTION_TEMPLATES["recipe_focus"] + CAPTION_TEMPLATES["process_focus"]
        
        template = rng.choice(templates)
        
        # Fill in the template
        caption = template.format(
            dish=dish_name.title(),
            time="30-minute" if meal_type == "weeknight" else "quick",
            relative="grandmother" if rng.random() > 0.5 else "mother",
            memory="happiness",
            emotion="comfort",
            option_a="this version" if rng.random() > 0.5 else "the classic",
            option_b="the spicy twist" if rng.random() > 0.5 else "the creamy one"
        )
        
        return caption
    
    def select_hashtags(
        self,
        content_type: Dict,
        count: int = 20,
        content_description: str = "",
        rng: Optional[random.Random] = None,
    ) -> List[str]:
        """
        Select optimal hashtags based on content type and current performance.
        Uses LLM if configured, otherwise falls back to template-based selection.
        """
        rng = rng or random.Random()
        # Try LLM first if available
        if LLM_AVAILABLE:
            try:
                description = content_description or f"{content_type.get('cuisine_type', '')} {content_type.get('meal_type', 'food')}"
                return llm_generate_hashtags(
                    content_description=description,
                    content_type=content_type.get("meal_type", "food"),
                    cuisine=content_type.get("cuisine_type"),
                    count=count
                )
            except Exception as e:
                logger.warning(f"LLM hashtag generation failed, using templates: {e}")
        
        # Fall back to template-based selection
        selected = []
        
        # Get database stats for hashtag performance
        c = self.conn.cursor()
        c.execute("SELECT hashtag FROM hashtag_performance ORDER BY avg_engagement DESC LIMIT 10")
        performing_tags = [row[0] for row in c.fetchall()]
        
        # Mix of hashtag types for optimal reach
        # 5-7 high volume (discovery)
        high_volume_sample = rng.sample(HASHTAG_CATEGORIES["high_volume"], 
                                        min(6, len(HASHTAG_CATEGORIES["high_volume"])))
        selected.extend(high_volume_sample)
        
        # 8-10 niche (targeted audience)
        niche_sample = rng.sample(HASHTAG_CATEGORIES["niche"], 
                                  min(8, len(HASHTAG_CATEGORIES["niche"])))
        selected.extend(niche_sample)
        
        # 3-5 engagement-focused
        engagement_sample = rng.sample(HASHTAG_CATEGORIES["engagement"], 
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
    
    def recommend_posting_time(self, content_type: Dict, content_description: str = "") -> Dict:
        """
        Recommend optimal posting time based on content type and historical data
        """
        meal_type = content_type.get("meal_type") or "unknown"
        is_video = content_type.get("format") == "video"
        desc_lower = (content_description or "").lower()
        weekday = datetime.now().weekday()
        is_weekend = weekday >= 5
        
        # Base recommendation on meal type
        if meal_type == "breakfast":
            recommended_time = "09:00" if is_weekend else OPTIMAL_POST_TIMES["weekday_breakfast"]
            reasoning = "Breakfast content performs best when people are planning their morning meal."
        elif meal_type == "brunch":
            recommended_time = OPTIMAL_POST_TIMES["weekend_brunch"] if is_weekend else "10:30"
            reasoning = "Brunch-style content performs best in the late-morning craving window, especially for leisurely saves and shares."
        elif meal_type == "lunch":
            recommended_time = "13:00" if "office" in desc_lower or "work" in desc_lower else OPTIMAL_POST_TIMES["weekday_lunch"]
            reasoning = "Lunch content aligns with midday decision-making and lunch-break browsing."
        elif meal_type == "dessert/snack":
            recommended_time = "20:00" if "late night" in desc_lower or "dessert" in desc_lower else "15:00"
            reasoning = "Dessert and snack content performs around craving windows in the afternoon or after dinner."
        elif meal_type == "beverage":
            if any(word in desc_lower for word in ["coffee", "latte", "espresso", "tea"]):
                recommended_time = "08:30"
                reasoning = "Morning beverage content performs best when people are entering their first caffeine or cafe decision window."
            else:
                recommended_time = "17:00"
                reasoning = "Drinks content tends to perform best late afternoon, when social plans and cravings start forming."
        elif meal_type == "dinner":
            if is_weekend:
                recommended_time = OPTIMAL_POST_TIMES["weekend_dinner"]
                reasoning = "Weekend dinner content performs best earlier, when people plan evenings and outings."
            else:
                recommended_time = "17:30" if is_video else OPTIMAL_POST_TIMES["weekday_dinner"]
                reasoning = "Dinner content performs around planning and prep time on weekdays."
        else:
            recommended_time = "11:30" if not is_video else "16:30"
            reasoning = "The meal signal is unclear, so this uses a broader discovery window instead of assuming dinner."

        if is_video:
            reasoning += " Video-first posts benefit from slightly earlier distribution to build momentum."
        else:
            reasoning += " Static visuals tend to perform better closer to the meal planning moment."
        
        return {
            "time": recommended_time,
            "reasoning": reasoning,
            "timezone": "local",
            "engagement_prediction": "high" if meal_type in ["dinner", "dessert/snack"] or is_video else "medium"
        }

    def build_strategy_notes(
        self,
        content_type: Dict,
        visual_analysis: Optional[Dict],
        optimal_time: Dict,
    ) -> str:
        """Generate concise, grounded strategy notes from the available signals."""
        dish = content_type.get("dish_detected") or "the dish"
        meal_type = content_type.get("meal_type") or "general meal"
        cuisine = (content_type.get("cuisine_type") or "mixed").title()
        visual_summary = (visual_analysis or {}).get("visual_summary") or "The visual read is limited, so the strategy leans on dish and format cues."
        format_name = "video" if content_type.get("format") == "video" else "image"

        if format_name == "video":
            hook = "Use motion and texture as the main growth lever. The first 1-2 seconds should show the strongest sensory moment."
            win_condition = "This should optimize for replays, saves, and shares."
        else:
            hook = "Lead with appetite and clarity. The frame needs to sell texture, freshness, and brand taste in one glance."
            win_condition = "This should optimize for profile taps and saves."

        mismatch_note = ""
        if visual_analysis and visual_analysis.get("contradicts_user_text"):
            mismatch_note = " The uploaded visual and the typed context appear to conflict, so confidence is intentionally reduced."

        return (
            f"Visual read: {visual_summary} "
            f"For {dish} in the {meal_type} window, position it as {cuisine} {format_name} content with a clear craving hook. "
            f"{hook} Post around {optimal_time['time']} because that window best matches when people decide on or crave this type of content. "
            f"{win_condition}{mismatch_note}"
        )
    
    def generate_strategy_notes(self, content_type: Dict, content_description: str = "", seed: str = "") -> str:
        """
        Generate strategic notes explaining why this recommendation was made
        """
        rng = self._get_rng(seed or content_description or "strategy")
        preferred_patterns = [
            pattern for pattern in HIGH_PERFORMANCE_PATTERNS
            if (
                content_type.get("format") == "video" and pattern["best_for"] in ["Recipe tutorials", "Reels content", "Snackable content"]
            ) or (
                content_type.get("format") != "video" and pattern["best_for"] in ["Photo posts", "Visual impact posts"]
            )
        ] or HIGH_PERFORMANCE_PATTERNS[:2]

        selected_pattern = rng.choice(preferred_patterns)
        cuisine = (content_type.get('cuisine_type') or 'mixed').title()
        meal_type = (content_type.get('meal_type') or 'general').title()
        focus = "save-friendly teaching" if content_type.get("format") == "video" else "high-intent visual appeal"

        notes = f"""
        STRATEGIC RECOMMENDATION:

        Content Type: {meal_type} | {cuisine} Cuisine | {content_type.get('format', 'image').title()} Format

        Why this approach:
        1. This content best matches the "{selected_pattern['type']}" pattern
           which typically drives {selected_pattern['engagement_boost']}

        2. The caption variants balance appetite appeal with a stronger engagement hook

        3. The hashtag variants split between broad discovery and more targeted niche reach

        4. Posting time aligns with when your audience is most likely planning or craving this meal

        Expected outcome: Better {focus}, stronger saves, and more profile visits.
        """

        return notes.strip()

    def build_caption_variants(self, content_type: Dict, content_description: str, seed: str) -> List[Dict]:
        """Build two caption variants with different tones."""
        variant_specs = [
            ("Performance", "engagement"),
            ("Story-led", "story" if content_description else "process"),
        ]
        variants = []
        for index, (label, strategy) in enumerate(variant_specs):
            variant_seed = f"{seed}:caption:{index}:{strategy}"
            rng = self._get_rng(variant_seed)
            variants.append(
                {
                    "label": label,
                    "caption": self.generate_caption(
                        content_type,
                        strategy=strategy,
                        content_description=content_description,
                        rng=rng,
                    ),
                    "why": (
                        "Uses a stronger hook to drive saves and comments."
                        if strategy == "engagement"
                        else "Leans into story and relatability to create a warmer brand voice."
                    ),
                }
            )
        return variants

    def build_hashtag_variants(self, content_type: Dict, content_description: str, seed: str) -> List[Dict]:
        """Build two hashtag mixes for discovery vs targeted reach."""
        base_tags = self.select_hashtags(
            content_type,
            content_description=content_description,
            rng=self._get_rng(f"{seed}:hashtags:base"),
        )

        cuisine = content_type.get("cuisine_type")
        meal_type = content_type.get("meal_type")
        niche_boosters = [tag for tag in [f"{cuisine}food" if cuisine else None, meal_type] if tag]

        discovery = list(dict.fromkeys(base_tags[:12] + ["instafood", "foodie", "foodstagram"]))[:15]
        targeted = list(dict.fromkeys(niche_boosters + base_tags[6:18] + ["recipeideas", "homecooking"]))[:15]

        return [
            {
                "label": "Broader Discovery",
                "hashtags": discovery,
                "why": "Leans on larger food discovery tags to maximize reach.",
            },
            {
                "label": "Targeted Intent",
                "hashtags": targeted,
                "why": "Focuses on meal and cuisine intent to improve relevance and saves.",
            },
        ]

    def build_thinking_sections(
        self,
        content_type: Dict,
        optimal_time: Dict,
        confidence: float,
        strategy_notes: str,
    ) -> List[Dict]:
        """Return collapsed reasoning blocks for the UI."""
        return [
            {
                "title": "Content Read",
                "content": (
                    f"Detected {content_type.get('format', 'image')} content for "
                    f"{content_type.get('meal_type') or 'general'} with "
                    f"{content_type.get('cuisine_type') or 'mixed'} cuisine signals."
                ),
            },
            {
                "title": "Timing Logic",
                "content": optimal_time.get("reasoning", "Timing based on content type and meal window."),
            },
            {
                "title": "Strategy Notes",
                "content": strategy_notes,
            },
            {
                "title": "Confidence Breakdown",
                "content": (
                    f"Confidence landed at {round(confidence * 100)}% based on detected meal type, "
                    f"cuisine clues, provided context, and media format clarity."
                ),
            },
        ]


async def analyze_and_recommend(
    content_id: str, 
    filepath: str, 
    user_caption: Optional[str] = None,
    context: Optional[str] = None
) -> Dict:
    """
    Main entry point: Analyze content and return full recommendation
    
    Args:
        content_id: Unique content identifier
        filepath: Path to the uploaded file
        user_caption: Optional user-provided caption
        context: Additional context about the content (dish description, recipe, story)
    """
    analyzer = ContentAnalyzer()
    seed = f"{content_id}:{filepath}:{user_caption or ''}:{context or ''}"
    description = context or user_caption or ""
    visual_analysis = None

    if LLM_AVAILABLE:
        try:
            visual_analysis = llm_analyze_visual_asset(
                filepath,
                user_caption=user_caption,
                context=context,
            )
        except Exception as e:
            logger.warning(f"Visual analysis failed, continuing without image facts: {e}")

    # Detect content type
    content_type = analyzer.refine_content_type(filepath, user_caption, context, visual_analysis)
    description = analyzer.build_visual_description(visual_analysis, user_caption, context) or description

    if visual_analysis and visual_analysis.get("food_present") is False:
        return analyzer.build_non_food_response(content_id, content_type, visual_analysis)

    caption_variants = analyzer.build_caption_variants(content_type, description, seed)
    hashtag_variants = analyzer.build_hashtag_variants(content_type, description, seed)
    caption = caption_variants[0]["caption"]
    hashtags = hashtag_variants[0]["hashtags"]
    time_rec = analyzer.recommend_posting_time(content_type, description)
    strategy_notes = analyzer.build_strategy_notes(content_type, visual_analysis, time_rec)
    
    # Calculate confidence based on content clarity
    confidence = content_type["confidence"]
    if user_caption:
        confidence += 0.08
    if context:
        confidence += 0.12
    if content_type.get("meal_type"):
        confidence += 0.05
    if content_type.get("cuisine_type"):
        confidence += 0.03
    if content_type.get("format") == "video":
        confidence += 0.02
    confidence = min(confidence, 1.0)
    thinking_sections = analyzer.build_thinking_sections(
        content_type,
        time_rec,
        confidence,
        strategy_notes,
    )
    
    return {
        "content_id": content_id,
        "content_analysis": content_type,
        "suggested_caption": caption,
        "suggested_hashtags": hashtags,
        "caption_variants": caption_variants,
        "hashtag_variants": hashtag_variants,
        "optimal_time": time_rec,
        "strategy_notes": strategy_notes,
        "confidence_score": round(confidence, 2),
        "content_patterns": [p["type"] for p in HIGH_PERFORMANCE_PATTERNS[:3]],
        "thinking_sections": thinking_sections,
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
