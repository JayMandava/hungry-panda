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
import re
import time
from collections import deque
from dataclasses import dataclass, field

# Optional LLM integration
try:
    from integrations.llm_client import (
        analyze_visual_asset as llm_analyze_visual_asset,
        generate_caption as llm_generate_caption,
        generate_hashtags as llm_generate_hashtags,
        generate_post_recommendation as llm_generate_post_recommendation,
    )
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

logger = logging.getLogger(__name__)

# Recommendation outcome tracking
RECOMMENDATION_STATS = {
    "total": 0,
    "structured_attempts": 0,
    "structured_successes": 0,
    "by_source": {
        "llm_structured": 0,
        "llm_fallback": 0,
        "template": 0,
    },
}

# Per-stage timing metrics (rolling window of last 100 requests)
@dataclass
class StageTiming:
    """Tracks timing for a single stage"""
    name: str
    durations: deque = field(default_factory=lambda: deque(maxlen=100))
    count: int = 0
    total_time: float = 0.0
    
    def record(self, duration_ms: float):
        self.durations.append(duration_ms)
        self.count += 1
        self.total_time += duration_ms
    
    @property
    def avg_ms(self) -> float:
        if not self.durations:
            return 0.0
        return sum(self.durations) / len(self.durations)
    
    @property
    def p95_ms(self) -> float:
        if len(self.durations) < 20:
            return self.avg_ms
        sorted_durations = sorted(self.durations)
        idx = int(len(sorted_durations) * 0.95)
        return sorted_durations[min(idx, len(sorted_durations) - 1)]
    
    def to_dict(self) -> Dict:
        return {
            "avg_ms": round(self.avg_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "count": self.count,
            "total_ms": round(self.total_time, 2),
        }


# Global stage timing registry
STAGE_TIMINGS: Dict[str, StageTiming] = {}
LLM_CALL_COUNTS: Dict[str, int] = {
    "visual_analysis": 0,
    "structured_recommendation": 0,
    "caption_generation": 0,
    "hashtag_generation": 0,
    "visual_detail": 0,
}


class StageTimer:
    """Context manager for timing a stage"""
    def __init__(self, stage_name: str):
        self.stage_name = stage_name
        self.start_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000
        
        # Record in stage timings
        if self.stage_name not in STAGE_TIMINGS:
            STAGE_TIMINGS[self.stage_name] = StageTiming(self.stage_name)
        STAGE_TIMINGS[self.stage_name].record(self.duration_ms)
        
        # Log the timing
        logger.info(
            "Stage timing: %s took %.2fms",
            self.stage_name,
            self.duration_ms
        )
        return False  # Don't suppress exceptions


def get_stage_timings() -> Dict[str, Dict]:
    """Return all stage timing metrics"""
    return {
        name: timing.to_dict()
        for name, timing in STAGE_TIMINGS.items()
    }


def get_llm_call_counts() -> Dict[str, int]:
    """Return LLM call counts"""
    return dict(LLM_CALL_COUNTS)


def reset_llm_call_counts():
    """Reset LLM call counts (for testing)"""
    global LLM_CALL_COUNTS
    LLM_CALL_COUNTS = {k: 0 for k in LLM_CALL_COUNTS}


def increment_llm_call_count(call_type: str):
    """Increment count for a specific LLM call type"""
    if call_type in LLM_CALL_COUNTS:
        LLM_CALL_COUNTS[call_type] += 1


def get_inference_metrics() -> Dict:
    """Return comprehensive inference metrics for health/debug endpoint"""
    return {
        "stage_timings": get_stage_timings(),
        "llm_call_counts": get_llm_call_counts(),
        "recommendation_stats": get_recommendation_stats(),
    }

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


def record_recommendation_outcome(
    source: str,
    structured_attempted: bool = False,
    structured_success: bool = False,
) -> None:
    """Track which recommendation path produced the final result."""
    RECOMMENDATION_STATS["total"] += 1
    RECOMMENDATION_STATS["by_source"][source] = RECOMMENDATION_STATS["by_source"].get(source, 0) + 1
    if structured_attempted:
        RECOMMENDATION_STATS["structured_attempts"] += 1
    if structured_success:
        RECOMMENDATION_STATS["structured_successes"] += 1

    logger.info(
        "Recommendation source=%s structured_attempted=%s structured_success=%s",
        source,
        structured_attempted,
        structured_success,
    )


def get_recommendation_stats() -> Dict[str, object]:
    """Return lightweight recommendation pipeline counters for health reporting."""
    attempts = RECOMMENDATION_STATS["structured_attempts"]
    successes = RECOMMENDATION_STATS["structured_successes"]
    success_rate = round(successes / attempts, 4) if attempts else None
    return {
        "total": RECOMMENDATION_STATS["total"],
        "structured_attempts": attempts,
        "structured_successes": successes,
        "structured_rec_success_rate": success_rate,
        "by_source": dict(RECOMMENDATION_STATS["by_source"]),
    }

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
        recommendation_source: str = "template",
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
            "recommendation_source": recommendation_source,
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

        optimal_time = llm_result.get("optimal_time")
        if not isinstance(optimal_time, dict) or not optimal_time.get("time"):
            fallback_time = self.recommend_posting_time(content_type, description)
            optimal_time = fallback_time
        else:
            fallback_time = optimal_time

        strategy_notes = (llm_result.get("strategy_notes") or "").strip()
        if not strategy_notes:
            strategy_notes = self.build_strategy_notes(content_type, None, optimal_time)
        confidence_payload = self.score_recommendation_quality(
            caption_variants,
            hashtag_variants,
            optimal_time,
            strategy_notes,
            recommendation_source="llm_structured",
        )
        confidence = confidence_payload["score"]
        thinking_sections = llm_result.get("thinking_sections") or self.build_thinking_sections(
            content_type,
            optimal_time,
            confidence,
            strategy_notes,
            confidence_payload["reasoning"],
        )
        content_patterns = llm_result.get("content_patterns") or [p["type"] for p in HIGH_PERFORMANCE_PATTERNS[:3]]

        return {
            "content_id": content_id,
            "content_analysis": content_type,
            "recommendation_source": "llm_structured",
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
            "confidence_reasoning": confidence_payload["reasoning"],
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

    def _caption_quality_score(self, captions: List[str]) -> float:
        """Score how specific and usable the generated captions are."""
        if not captions:
            return 0.2

        meta_markers = {
            "the user wants",
            "requirements",
            "strategy",
            "option 1",
            "option 2",
            "let me",
            "return exactly",
        }
        total = 0.0
        for caption in captions:
            text = (caption or "").strip()
            lower = text.lower()
            score = 0.35

            if len(text.split()) >= 8:
                score += 0.2
            if len(text.split()) <= 40:
                score += 0.1
            if any(char in text for char in "?!"):
                score += 0.08
            if any(char in text for char in "🍕🍛🍜🍔🥘☕🍰🌮🍝🥞"):
                score += 0.05
            if re.search(r"\b(save|tag|comment|tell me|follow|try|craving)\b", lower):
                score += 0.12
            if len(set(re.findall(r"[a-z0-9]+", lower))) >= 8:
                score += 0.1
            if any(marker in lower for marker in meta_markers):
                score -= 0.45
            total += max(0.0, min(score, 1.0))
        return total / len(captions)

    def _hashtag_quality_score(self, hashtag_variants: List[Dict]) -> float:
        """Score hashtag usefulness based on volume, cleanliness, and variant spread."""
        if not hashtag_variants:
            return 0.15

        total = 0.0
        planning_words = {"optimized", "generate", "instagram", "hashtags", "specific", "post", "break", "down"}
        for variant in hashtag_variants:
            tags = [str(tag).strip().lstrip("#") for tag in (variant.get("hashtags") or []) if str(tag).strip()]
            if not tags:
                continue

            score = 0.3
            unique_tags = list(dict.fromkeys(tags))
            if len(unique_tags) >= 10:
                score += 0.25
            elif len(unique_tags) >= 6:
                score += 0.15

            clean_tags = [tag for tag in unique_tags if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_]{1,40}", tag)]
            score += 0.2 * (len(clean_tags) / max(len(unique_tags), 1))

            if len({tag.lower() for tag in unique_tags}) == len(unique_tags):
                score += 0.08
            if not any(tag.lower() in planning_words for tag in unique_tags):
                score += 0.12
            total += max(0.0, min(score, 1.0))

        variant_score = total / max(len(hashtag_variants), 1)
        if len(hashtag_variants) >= 2:
            first = {tag.lower() for tag in hashtag_variants[0].get("hashtags", [])}
            second = {tag.lower() for tag in hashtag_variants[1].get("hashtags", [])}
            overlap = len(first & second) / max(len(first | second), 1)
            variant_score += max(0.0, 0.1 - overlap * 0.1)
        return max(0.0, min(variant_score, 1.0))

    def _time_quality_score(self, optimal_time: Dict) -> float:
        """Score whether timing output looks specific and properly reasoned."""
        if not isinstance(optimal_time, dict):
            return 0.2

        score = 0.25
        time_value = str(optimal_time.get("time") or "").strip()
        reasoning = str(optimal_time.get("reasoning") or "").strip()

        if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", time_value):
            score += 0.25
        if len(reasoning.split()) >= 12:
            score += 0.2
        if re.search(r"\b(craving|window|audience|save|share|prep|decision|commute|planning)\b", reasoning.lower()):
            score += 0.2
        if "based on follower activity patterns" not in reasoning.lower():
            score += 0.05
        return max(0.0, min(score, 1.0))

    def _strategy_quality_score(self, strategy_notes: str) -> float:
        """Score how actionable and non-generic the strategy note is."""
        text = (strategy_notes or "").strip()
        if not text:
            return 0.15

        lower = text.lower()
        score = 0.3
        if len(text.split()) >= 20:
            score += 0.2
        if re.search(r"\b(post|hook|save|share|follow|profile|craving|texture|timing|audience)\b", lower):
            score += 0.2
        if re.search(r"\b(dish|pizza|dosa|curry|biryani|pasta|coffee|dessert|meal)\b", lower):
            score += 0.1
        if "strategic recommendation" not in lower:
            score += 0.08
        if "visual read is limited" in lower:
            score -= 0.08
        return max(0.0, min(score, 1.0))

    def _variant_distinction_score(self, caption_variants: List[Dict], hashtag_variants: List[Dict]) -> float:
        """Score whether the paired variants are meaningfully different."""
        score = 0.45

        if len(caption_variants) >= 2:
            first = set(re.findall(r"[a-z0-9]+", caption_variants[0].get("caption", "").lower()))
            second = set(re.findall(r"[a-z0-9]+", caption_variants[1].get("caption", "").lower()))
            caption_overlap = len(first & second) / max(len(first | second), 1)
            score += max(0.0, 0.25 - caption_overlap * 0.25)

        if len(hashtag_variants) >= 2:
            first_tags = {tag.lower() for tag in hashtag_variants[0].get("hashtags", [])}
            second_tags = {tag.lower() for tag in hashtag_variants[1].get("hashtags", [])}
            tag_overlap = len(first_tags & second_tags) / max(len(first_tags | second_tags), 1)
            score += max(0.0, 0.2 - tag_overlap * 0.2)

        return max(0.0, min(score, 1.0))

    def score_recommendation_quality(
        self,
        caption_variants: List[Dict],
        hashtag_variants: List[Dict],
        optimal_time: Dict,
        strategy_notes: str,
        recommendation_source: str,
    ) -> Dict[str, str]:
        """Score recommendation quality from the generated output itself."""
        caption_score = self._caption_quality_score([item.get("caption", "") for item in caption_variants])
        hashtag_score = self._hashtag_quality_score(hashtag_variants)
        time_score = self._time_quality_score(optimal_time)
        strategy_score = self._strategy_quality_score(strategy_notes)
        distinction_score = self._variant_distinction_score(caption_variants, hashtag_variants)

        overall = (
            caption_score * 0.28
            + hashtag_score * 0.2
            + time_score * 0.2
            + strategy_score * 0.2
            + distinction_score * 0.12
        )

        if recommendation_source == "template":
            overall *= 0.82
        elif recommendation_source == "llm_fallback":
            overall *= 0.9

        overall = max(0.12, min(overall, 0.96))
        reasoning = (
            f"Scored from output quality: captions {round(caption_score * 100)}%, "
            f"hashtags {round(hashtag_score * 100)}%, timing {round(time_score * 100)}%, "
            f"strategy {round(strategy_score * 100)}%, variant separation {round(distinction_score * 100)}%."
        )
        return {"score": overall, "reasoning": reasoning}
    
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
        use_llm: bool = True,
    ) -> str:
        """
        Generate an optimized caption based on content type and strategy.
        Uses LLM if configured, otherwise falls back to templates.
        
        Args:
            use_llm: If False, skip LLM and use templates directly (for fallback mode)
        """
        rng = rng or random.Random()
        meal_type = content_type.get("meal_type", "dinner")
        cuisine = content_type.get("cuisine_type", "homestyle")
        dish_name = content_type.get("dish_detected") or f"{cuisine} {meal_type}".strip()
        
        # Try LLM first if available AND use_llm is True
        if LLM_AVAILABLE and use_llm:
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
        
        # Fall back to template-based generation (guaranteed local, no LLM)
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
        use_llm: bool = True,
    ) -> List[str]:
        """
        Select optimal hashtags based on content type and current performance.
        Uses LLM if configured, otherwise falls back to template-based selection.
        
        Args:
            use_llm: If False, skip LLM and use templates directly (for fallback mode)
        """
        rng = rng or random.Random()
        # Try LLM first if available AND use_llm is True
        if LLM_AVAILABLE and use_llm:
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
        
        # Fall back to template-based selection (guaranteed local, no LLM)
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
    
    def _get_best_engagement_hour(self, meal_type: Optional[str]) -> Optional[str]:
        """Query historical post data to find the best-performing hour for this meal type."""
        try:
            c = self.conn.cursor()
            c.execute(
                """
                SELECT strftime('%H', posted_time) AS hour,
                       AVG(likes + comments * 2 + saves * 3) AS score
                FROM content
                WHERE posted_time IS NOT NULL
                  AND status = 'posted'
                  AND likes + comments + saves > 0
                  AND (content_type = ? OR ? IS NULL)
                GROUP BY hour
                HAVING COUNT(*) >= 2
                ORDER BY score DESC
                LIMIT 1
                """,
                (meal_type, meal_type),
            )
            row = c.fetchone()
            if row and row[0]:
                return f"{int(row[0]):02d}:00"
        except Exception:
            pass
        return None

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

        # Override with account-specific engagement history when enough data exists
        best_hour = self._get_best_engagement_hour(meal_type if meal_type != "unknown" else None)
        if best_hour:
            recommended_time = best_hour
            reasoning += f" Your account's historical engagement data points to {best_hour} as the top-performing window for {meal_type} posts."

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

    def build_caption_variants(self, content_type: Dict, content_description: str, seed: str, use_llm: bool = True) -> List[Dict]:
        """Build two caption variants with different tones.
        
        Args:
            use_llm: If False, use template-based generation only (for fallback mode)
        """
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
                        use_llm=use_llm,
                    ),
                    "why": (
                        "Uses a stronger hook to drive saves and comments."
                        if strategy == "engagement"
                        else "Leans into story and relatability to create a warmer brand voice."
                    ),
                }
            )
        return variants

    def build_hashtag_variants(self, content_type: Dict, content_description: str, seed: str, use_llm: bool = True) -> List[Dict]:
        """Build two hashtag mixes for discovery vs targeted reach.
        
        Args:
            use_llm: If False, use template-based generation only (for fallback mode)
        """
        base_tags = self.select_hashtags(
            content_type,
            content_description=content_description,
            rng=self._get_rng(f"{seed}:hashtags:base"),
            use_llm=use_llm,
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
        confidence_reasoning: Optional[str] = None,
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
                "content": confidence_reasoning or (
                    f"Confidence landed at {round(confidence * 100)}% based on the strength, specificity, "
                    f"and distinctness of the generated recommendation."
                ),
            },
        ]


async def analyze_and_recommend(
    content_id: str, 
    filepath: str, 
    user_caption: Optional[str] = None,
    context: Optional[str] = None,
    _request_metrics: Optional[Dict] = None,
) -> Dict:
    """
    Main entry point: Analyze content and return full recommendation
    
    Args:
        content_id: Unique content identifier
        filepath: Path to the uploaded file
        user_caption: Optional user-provided caption
        context: Additional context about the content (dish description, recipe, story)
        _request_metrics: Optional dict to return per-request metrics (for testing/debug)
    """
    request_start = time.perf_counter()
    request_metrics = {
        "content_id": content_id,
        "stages": {},
        "llm_calls": 0,
        "total_duration_ms": 0,
    }
    
    # Track actual per-request stage durations (not rolling averages)
    request_stage_durations: Dict[str, float] = {}
    
    analyzer = ContentAnalyzer()
    seed = f"{content_id}:{filepath}:{user_caption or ''}:{context or ''}"
    description = context or user_caption or ""
    visual_analysis = None

    # Helper to capture actual per-request duration
    def capture_stage_duration(stage_name: str, start_time: float) -> float:
        duration_ms = (time.perf_counter() - start_time) * 1000
        request_stage_durations[stage_name] = duration_ms
        return duration_ms

    # Stage 1: Media preprocessing (if any)
    stage_start = time.perf_counter()
    with StageTimer("media_preprocessing"):
        # Preprocessing happens lazily in llm_analyze_visual_asset via _build_image_data_url
        pass
    request_metrics["stages"]["media_preprocessing"] = round(capture_stage_duration("media_preprocessing", stage_start), 2)

    # Stage 2: Visual analysis (first LLM call)
    stage_start = time.perf_counter()
    if LLM_AVAILABLE:
        try:
            with StageTimer("visual_analysis"):
                increment_llm_call_count("visual_analysis")
                request_metrics["llm_calls"] += 1  # Count attempted call
                visual_analysis = llm_analyze_visual_asset(
                    filepath,
                    user_caption=user_caption,
                    context=context,
                )
            request_metrics["stages"]["visual_analysis"] = round(capture_stage_duration("visual_analysis", stage_start), 2)
        except Exception as e:
            logger.warning(f"Visual analysis failed, continuing without image facts: {e}")
            request_metrics["stages"]["visual_analysis"] = None
            request_stage_durations["visual_analysis"] = round((time.perf_counter() - stage_start) * 1000, 2)

    # Stage 3: Content type detection (local, no LLM)
    stage_start = time.perf_counter()
    with StageTimer("content_type_detection"):
        content_type = analyzer.refine_content_type(filepath, user_caption, context, visual_analysis)
        description = analyzer.build_visual_description(visual_analysis, user_caption, context) or description
    request_metrics["stages"]["content_type_detection"] = round(capture_stage_duration("content_type_detection", stage_start), 2)

    # Stage 4: Primary path - structured recommendation (second LLM call)
    # CRITICAL: Only proceed if visual_analysis succeeded. If visual_analysis is None,
    # llm_generate_post_recommendation would internally call _inspect_visual_asset again,
    # violating the 2-call max guarantee (we'd have: failed visual + internal visual + structured = 3 calls).
    stage_start = time.perf_counter()
    if LLM_AVAILABLE and visual_analysis is not None:
        try:
            with StageTimer("structured_recommendation"):
                increment_llm_call_count("structured_recommendation")
                request_metrics["llm_calls"] += 1  # Count attempted call
                # Pass visual_analysis explicitly - never let generate_post_recommendation 
                # make an internal visual call. This enforces the 2-call max.
                llm_result = llm_generate_post_recommendation(
                    filepath,
                    user_caption=user_caption,
                    context=context,
                    fallback_analysis=dict(content_type),
                    visual_analysis=visual_analysis,  # Never None here
                    _allow_internal_visual=False,  # Enforce 2-call max - never re-enter vision
                )
            request_metrics["stages"]["structured_recommendation"] = round(capture_stage_duration("structured_recommendation", stage_start), 2)
            
            # Stage 5: Normalize recommendation (local processing)
            norm_start = time.perf_counter()
            with StageTimer("normalize_recommendation"):
                result = analyzer.normalize_llm_recommendation(content_id, filepath, user_caption, context, llm_result)
            request_metrics["stages"]["normalize_recommendation"] = round(capture_stage_duration("normalize_recommendation", norm_start), 2)
            
            record_recommendation_outcome("llm_structured", structured_attempted=True, structured_success=True)
            
            request_metrics["total_duration_ms"] = round((time.perf_counter() - request_start) * 1000, 2)
            if _request_metrics is not None:
                _request_metrics.update(request_metrics)
            
            logger.info(
                "Request %s completed: llm_calls=%d, total=%.2fms, request_stage_durations=%s",
                content_id,
                request_metrics["llm_calls"],
                request_metrics["total_duration_ms"],
                request_stage_durations,
            )
            return result
        except Exception as e:
            logger.warning(f"Structured recommendation failed, falling back to separate calls: {e}")
            request_metrics["stages"]["structured_recommendation"] = None
            request_stage_durations["structured_recommendation"] = round((time.perf_counter() - stage_start) * 1000, 2)

    # Stage 6: Fallback path - local-only generation (NO additional LLM calls)
    # CRITICAL: use_llm=False ensures we don't make any additional LLM calls during fallback
    fallback_start = time.perf_counter()
    with StageTimer("fallback_generation"):
        caption_variants = analyzer.build_caption_variants(content_type, description, seed, use_llm=False)
        hashtag_variants = analyzer.build_hashtag_variants(content_type, description, seed, use_llm=False)
        caption = caption_variants[0]["caption"]
        hashtags = hashtag_variants[0]["hashtags"]
        time_rec = analyzer.recommend_posting_time(content_type, description)
        strategy_notes = analyzer.build_strategy_notes(content_type, visual_analysis, time_rec)
        source = "llm_fallback" if LLM_AVAILABLE else "template"
        confidence_payload = analyzer.score_recommendation_quality(
            caption_variants,
            hashtag_variants,
            time_rec,
            strategy_notes,
            recommendation_source=source,
        )
        confidence = confidence_payload["score"]
        thinking_sections = analyzer.build_thinking_sections(
            content_type,
            time_rec,
            confidence,
            strategy_notes,
            confidence_payload["reasoning"],
        )
    request_metrics["stages"]["fallback_generation"] = round(capture_stage_duration("fallback_generation", fallback_start), 2)
    record_recommendation_outcome(source, structured_attempted=LLM_AVAILABLE, structured_success=False)
    
    request_metrics["total_duration_ms"] = round((time.perf_counter() - request_start) * 1000, 2)
    if _request_metrics is not None:
        _request_metrics.update(request_metrics)
    
    logger.info(
        "Request %s completed (fallback): llm_calls=%d, total=%.2fms, request_stage_durations=%s",
        content_id,
        request_metrics["llm_calls"],
        request_metrics["total_duration_ms"],
        request_stage_durations,
    )

    return {
        "content_id": content_id,
        "content_analysis": content_type,
        "recommendation_source": source,
        "suggested_caption": caption,
        "suggested_hashtags": hashtags,
        "caption_variants": caption_variants,
        "hashtag_variants": hashtag_variants,
        "optimal_time": time_rec,
        "strategy_notes": strategy_notes,
        "confidence_score": round(confidence, 2),
        "confidence_reasoning": confidence_payload["reasoning"],
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
