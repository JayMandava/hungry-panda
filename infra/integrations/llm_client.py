"""
LLM Client for Hungry Panda
Supports multiple providers: Fireworks AI (Kimi K2.5), OpenAI
"""
import base64
import hashlib
import io
import json
import logging
from pathlib import Path
import re
import subprocess
from typing import Dict, List, Optional, Any, Tuple
import requests
from PIL import Image, ImageOps, UnidentifiedImageError

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    HEIF_AVAILABLE = False

try:
    import imageio_ffmpeg
    VIDEO_FRAME_EXTRACTION_AVAILABLE = True
except ImportError:
    VIDEO_FRAME_EXTRACTION_AVAILABLE = False

from infra.config.settings import config

logger = logging.getLogger(__name__)

VALID_MEAL_TYPES = {
    "breakfast",
    "brunch",
    "lunch",
    "dinner",
    "dessert/snack",
    "beverage",
    "unknown",
}


class LLMError(Exception):
    """Custom exception for LLM errors"""
    pass


class LLMClient:
    """
    Unified LLM client supporting multiple providers.
    
    Primary: Fireworks AI (Kimi K2.5)
    Fallback: OpenAI
    
    Features:
    - Persistent HTTP session for connection reuse (reduces latency on repeated calls)
    - 2-call max enforcement for recommendation flow
    """
    
    # Class-level session for connection reuse across instances
    _session: Optional[requests.Session] = None
    
    # Visual analysis cache: {(file_hash, mtime): vision_only_result}
    # P1: Cache visual analysis by file hash to avoid repeated vision calls
    # CRITICAL: Only caches visual facts (food_present, dish, meal_type, etc.)
    # Does NOT cache text-dependent fields (contradicts_user_text, mismatch_note)
    _visual_analysis_cache: Dict[Tuple[str, float], Dict[str, Any]] = {}
    _visual_cache_hits: int = 0
    _visual_cache_misses: int = 0
    _visual_cache_max_size: int = 100  # Bounded cache for long-running server
    
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or config.LLM_PROVIDER
        self._validate_config()
        # Initialize session on first use
        if LLMClient._session is None:
            LLMClient._session = requests.Session()
    
    @classmethod
    def get_session(cls) -> requests.Session:
        """Get or create the shared HTTP session."""
        if cls._session is None:
            cls._session = requests.Session()
        return cls._session
    
    @classmethod
    def close_session(cls):
        """Close the shared HTTP session. Call on shutdown."""
        if cls._session is not None:
            cls._session.close()
            cls._session = None
    
    @classmethod
    def _compute_cache_key(cls, filepath: str) -> Tuple[str, float]:
        """Compute cache key from file metadata (mtime, size, path hash).
        
        Note: This uses metadata (mtime + size + path) not content hash for speed.
        Content hash would require reading the entire file; metadata check is instant.
        """
        path = Path(filepath)
        if not path.exists():
            return ("", 0.0)
        # Use mtime + file size + path for cache key (fast metadata check)
        stat = path.stat()
        key = f"{stat.st_mtime}:{stat.st_size}:{filepath}"
        # Hash the metadata key for compact storage
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        return (key_hash, stat.st_mtime)
    
    @classmethod
    def _get_cached_visual_analysis(cls, filepath: str, user_text: str = "") -> Optional[Dict[str, Any]]:
        """Get cached visual analysis if file hasn't changed.
        
        CRITICAL: Recomputes text-dependent fields (contradicts_user_text) fresh
        from cached visual facts + current user_text. Never returns stale mismatch judgments.
        """
        cache_key = cls._compute_cache_key(filepath)
        if cache_key in cls._visual_analysis_cache:
            cls._visual_cache_hits += 1
            # Get cached visual facts (image-only analysis)
            cached_vision = cls._visual_analysis_cache[cache_key]
            # Recompute text-dependent fields fresh with current user_text
            result = dict(cached_vision)
            result["contradicts_user_text"] = cls._check_text_visual_mismatch(
                result.get("dish_detected", ""),
                result.get("meal_type", "unknown"),
                user_text
            )
            logger.info(f"Visual analysis cache HIT for {Path(filepath).name} (mismatch recomputed)")
            return result
        cls._visual_cache_misses += 1
        return None
    
    @classmethod
    def _check_text_visual_mismatch(cls, dish_detected: str, meal_type: str, user_text: str) -> bool:
        """Check if user text contradicts visual analysis.
        
        Simple heuristics: if user mentions a different dish or meal type than visual.
        """
        if not user_text:
            return False
        user_lower = user_text.lower()
        mismatches = []
        # Check dish mismatch
        if dish_detected and dish_detected.lower() not in user_lower:
            # Check if user mentioned any specific dish
            dish_keywords = ["pizza", "pasta", "burger", "salad", "curry", "dosa", "sushi", "ramen", "taco", "burrito"]
            user_dish = next((d for d in dish_keywords if d in user_lower), None)
            if user_dish and user_dish != dish_detected.lower():
                mismatches.append(f"visual={dish_detected}, text={user_dish}")
        # Check meal type mismatch
        if meal_type and meal_type != "unknown":
            opposite_meals = {
                "breakfast": ["dinner", "dessert"],
                "dinner": ["breakfast", "brunch"],
            }
            opposites = opposite_meals.get(meal_type, [])
            if any(m in user_lower for m in opposites):
                mismatches.append(f"visual={meal_type}, text mentions {opposites}")
        return len(mismatches) > 0
    
    @classmethod
    def _cache_visual_analysis(cls, filepath: str, analysis: Dict[str, Any]) -> None:
        """Cache visual analysis result for this file.
        
        CRITICAL: Strips text-dependent fields (contradicts_user_text, mismatch_note)
        before caching. Cache stores only visual facts about the image itself.
        """
        cache_key = cls._compute_cache_key(filepath)
        # Create vision-only copy (text-dependent fields computed at retrieval time)
        vision_only = {
            k: v for k, v in analysis.items()
            if k not in ("contradicts_user_text", "mismatch_note")
        }
        cls._visual_analysis_cache[cache_key] = vision_only
        
        # Bounded cache: evict oldest if at max size (simple LRU via dict ordering in Python 3.7+)
        while len(cls._visual_analysis_cache) > cls._visual_cache_max_size:
            cls._visual_analysis_cache.pop(next(iter(cls._visual_analysis_cache)))
        
        logger.info(f"Visual analysis cached for {Path(filepath).name} (vision-only fields, cache_size={len(cls._visual_analysis_cache)})")
    
    @classmethod
    def get_visual_cache_stats(cls) -> Dict[str, int]:
        """Return visual analysis cache statistics."""
        return {
            "hits": cls._visual_cache_hits,
            "misses": cls._visual_cache_misses,
            "size": len(cls._visual_analysis_cache),
            "hit_rate": round(cls._visual_cache_hits / max(cls._visual_cache_hits + cls._visual_cache_misses, 1), 2),
        }
    
    @classmethod
    def clear_visual_cache(cls):
        """Clear the visual analysis cache."""
        cls._visual_analysis_cache.clear()
        cls._visual_cache_hits = 0
        cls._visual_cache_misses = 0
    
    def _validate_config(self):
        """Validate LLM configuration"""
        if self.provider == "fireworks":
            if not config.FIREWORKS_API_KEY:
                raise LLMError("FIREWORKS_API_KEY not configured")
        elif self.provider == "openai":
            if not config.OPENAI_API_KEY:
                raise LLMError("OPENAI_API_KEY not configured")
        elif self.provider == "none":
            logger.info("LLM disabled - using template-based generation")
        else:
            raise LLMError(f"Unsupported LLM provider: {self.provider}")
    
    def generate_caption(
        self,
        content_description: str,
        content_type: str = "food",
        cuisine: Optional[str] = None,
        tone: str = "engaging"
    ) -> str:
        """
        Generate an Instagram caption using LLM.
        
        Args:
            content_description: Description of the food/content
            content_type: Type of content (food, recipe, dessert, etc.)
            cuisine: Cuisine type (italian, indian, etc.)
            tone: Tone of caption (engaging, storytelling, humorous, etc.)
            
        Returns:
            Generated caption string
        """
        if self.provider == "none":
            return self._template_caption(content_description, content_type, cuisine)
        
        # Compact prompt to reduce token payload
        system_prompt = "Create engaging food captions. Return JSON: {\"caption\": \"text\"}."
        
        user_prompt = f"""Write an Instagram caption for {content_type} food.

Content: {content_description}
Cuisine: {cuisine or 'general'}
Tone: {tone}

- Hook first, 2-4 emojis, CTA at end, under 100 words
- Return: {{"caption": "your caption here"}}"""

        try:
            response = self._call_llm(
                system_prompt,
                user_prompt,
                max_tokens=200,  # Reduced from 450: caption is ~100 words, ~150 tokens max
                timeout=45,
                json_mode=True,
            )
            cleaned = self._extract_json_string_field(response, "caption")
            cleaned = self._sanitize_caption_response(cleaned or "")
            if cleaned:
                return cleaned
            raise LLMError("Caption response contained meta-planning instead of a usable caption")
        except Exception as e:
            logger.error(f"LLM caption generation failed: {e}")
            return self._template_caption(content_description, content_type, cuisine)
    
    def generate_hashtags(
        self,
        content_description: str,
        content_type: str = "food",
        cuisine: Optional[str] = None,
        count: int = 20
    ) -> List[str]:
        """
        Generate optimized hashtags using LLM.
        
        Args:
            content_description: Description of content
            content_type: Type of content
            cuisine: Cuisine type
            count: Number of hashtags to generate
            
        Returns:
            List of hashtag strings (without #)
        """
        if self.provider == "none":
            return self._template_hashtags(content_type, cuisine, count)
        
        # Compact prompt to reduce token payload
        system_prompt = f"Generate {count} food hashtags. Return JSON: {{\"hashtags\": [\"...\"]}}."

        user_prompt = f"""Hashtags for {cuisine or 'food'} {content_type}.

Content: {content_description}

Mix: discovery (high-volume), niche (10K-100K), community. No # symbols.

Return: {{"hashtags": ["tag1", "tag2", ...]}}"""

        try:
            response = self._call_llm(
                system_prompt,
                user_prompt,
                max_tokens=300,  # Reduced from 700: 20 hashtags ~150 tokens, safe margin at 300
                timeout=45,
                json_mode=True,
            )
            hashtags = self._extract_json_string_list_field(response, "hashtags", count)
            if hashtags:
                return hashtags[:count]
            raise LLMError("Hashtag response contained meta-planning instead of a usable hashtag list")
        except Exception as e:
            logger.error(f"LLM hashtag generation failed: {e}")
            return self._template_hashtags(content_type, cuisine, count)

    def generate_post_recommendation(
        self,
        filepath: str,
        user_caption: Optional[str] = None,
        context: Optional[str] = None,
        fallback_analysis: Optional[Dict[str, Any]] = None,
        visual_analysis: Optional[Dict[str, Any]] = None,
        _allow_internal_visual: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a structured, growth-focused recommendation for a post.
        Uses image understanding when the uploaded asset is a supported image.
        Pass pre-computed visual_analysis to avoid a redundant vision call.
        
        Args:
            _allow_internal_visual: If False, raises error when visual_analysis is None
                                   instead of making an internal call. Used by the
                                   orchestration layer to enforce 2-call max guarantee.
        """
        if self.provider == "none":
            raise LLMError("LLM disabled - multimodal recommendation unavailable")

        if visual_analysis is None:
            if not _allow_internal_visual:
                raise LLMError(
                    "visual_analysis is None but _allow_internal_visual=False. "
                    "This would violate the 2-call max guarantee. "
                    "The orchestration layer should have provided visual_analysis or skipped this path."
                )
            visual_analysis = self._inspect_visual_asset(filepath, user_caption=user_caption, context=context)

        strategy_prompt = self._build_post_recommendation_prompt(
            filepath=filepath,
            user_caption=user_caption,
            context=context,
            fallback_analysis=fallback_analysis,
            visual_analysis=visual_analysis,
        )
        system_prompt = (
            "You are an Instagram growth strategist for food content. "
            "Return only valid JSON. No markdown. Use visual analysis as truth when it conflicts with user text."
        )

        # Tight token budget: structured output is ~1.2K tokens, 1.5K gives safe margin
        response = self._call_llm(
            system_prompt,
            strategy_prompt,
            max_tokens=1500,  # Reduced from 2000: JSON contract is ~1.2K tokens
            timeout=60,
            json_mode=True,
        )
        try:
            parsed = self._extract_json_object(response)
            self._validate_recommendation_payload(parsed)
        except LLMError:
            retry_prompt = (
                strategy_prompt
                + "\n\nCRITICAL: Your previous response was not valid JSON. "
                "Return ONLY the JSON object, starting with { and ending with }. No other text."
            )
            # Retry with same tight budget (P1 consistency)
            response = self._call_llm(
                system_prompt,
                retry_prompt,
                max_tokens=1500,  # Consistent with primary call (reduced from 2000)
                timeout=60,
                json_mode=True,
            )
            parsed = self._extract_json_object(response)
            self._validate_recommendation_payload(parsed)

        if not isinstance(parsed, dict):
            raise LLMError("Structured recommendation response was not a JSON object")
        return parsed

    def generate_reel_recommendation(
        self,
        filepath: str,
        user_caption: Optional[str] = None,
        context: Optional[str] = None,
        fallback_analysis: Optional[Dict[str, Any]] = None,
        visual_analysis: Optional[Dict[str, Any]] = None,
        _allow_internal_visual: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a structured, growth-focused recommendation for an Instagram Reel.
        Includes reel-specific fields: hook, on-screen text, CTA, and best practices.
        
        Args:
            filepath: Path to the video file
            user_caption: Optional user-provided caption
            context: Additional context about the content
            fallback_analysis: Pre-computed content analysis
            visual_analysis: Pre-computed visual analysis
            _allow_internal_visual: If False, raises error when visual_analysis is None
        """
        if self.provider == "none":
            raise LLMError("LLM disabled - multimodal recommendation unavailable")

        if visual_analysis is None:
            if not _allow_internal_visual:
                raise LLMError(
                    "visual_analysis is None but _allow_internal_visual=False. "
                    "This would violate the 2-call max guarantee."
                )
            visual_analysis = self._inspect_visual_asset(filepath, user_caption=user_caption, context=context)

        strategy_prompt = self._build_reel_recommendation_prompt(
            filepath=filepath,
            user_caption=user_caption,
            context=context,
            fallback_analysis=fallback_analysis,
            visual_analysis=visual_analysis,
        )
        system_prompt = (
            "You are an Instagram Reel strategist for food content. "
            "Return only valid JSON. No markdown. Focus on short-form video best practices."
        )

        response = self._call_llm(
            system_prompt,
            strategy_prompt,
            max_tokens=1800,
            timeout=60,
            json_mode=True,
        )
        try:
            parsed = self._extract_json_object(response)
            self._validate_reel_recommendation_payload(parsed)
        except LLMError:
            retry_prompt = (
                strategy_prompt
                + "\n\nCRITICAL: Your previous response was not valid JSON. "
                "Return ONLY the JSON object, starting with { and ending with }. No other text."
            )
            response = self._call_llm(
                system_prompt,
                retry_prompt,
                max_tokens=1800,
                timeout=60,
                json_mode=True,
            )
            parsed = self._extract_json_object(response)
            self._validate_reel_recommendation_payload(parsed)

        if not isinstance(parsed, dict):
            raise LLMError("Structured recommendation response was not a JSON object")
        return parsed

    def _build_reel_recommendation_prompt(
        self,
        filepath: str,
        user_caption: Optional[str],
        context: Optional[str],
        fallback_analysis: Optional[Dict[str, Any]],
        visual_analysis: Optional[Dict[str, Any]],
    ) -> str:
        """Build prompt for reel recommendation."""
        fallback_text = json.dumps(fallback_analysis or {}, ensure_ascii=True, separators=(',', ':'))
        visual_text = json.dumps(visual_analysis or {}, ensure_ascii=True, separators=(',', ':'))

        return f"""Analyze this Instagram Reel for growth.

Asset: {Path(filepath).name}
Caption: {user_caption or 'none'}
Context: {context or 'none'}
Visual: {visual_text}
Fallback: {fallback_text}

Rules for Reels:
- Hook must grab attention in first 3 seconds
- Keep captions punchy (under 150 chars for preview)
- Use trending audio references when relevant
- Include strong CTA for engagement
- Match posting time to meal type and audience activity
- Two caption variants: "Performance" (hook-first) and "Story-led" (brand voice)
- Two hashtag variants: "Broader Discovery" vs "Targeted Intent"
- Lower confidence if asset is ambiguous

Return JSON:
{{"content_analysis":{{"category":"...","dish_detected":"...","meal_type":"...","cuisine_type":"...","format":"reel","confidence":0.0}},"caption_variants":[{{"label":"Performance","caption":"...","why":"..."}},{{"label":"Story-led","caption":"...","why":"..."}}],"hashtag_variants":[{{"label":"Broader Discovery","hashtags":["..."],"why":"..."}},{{"label":"Targeted Intent","hashtags":["..."],"why":"..."}}],"optimal_time":{{"time":"HH:MM","reasoning":"...","timezone":"local","engagement_prediction":"low|medium|high"}},"reel_specific":{{"hook":"First 3-second grabber","on_screen_text":"Text overlay suggestion","cta":"Call to action","audio_suggestion":"Trending or thematic audio"}},"strategy_notes":"...","confidence_score":0.0,"content_patterns":["..."]}}"""

    def _validate_reel_recommendation_payload(self, parsed: Dict) -> None:
        """Validate reel recommendation structure."""
        required_fields = ["caption_variants", "hashtag_variants", "optimal_time", "reel_specific"]
        for field in required_fields:
            if field not in parsed:
                raise LLMError(f"Recommendation missing required field: {field}")

    def analyze_content_strategy(
        self,
        content_history: List[Dict],
        competitor_insights: Dict
    ) -> Dict[str, Any]:
        """
        Analyze content and provide strategic recommendations.
        
        Args:
            content_history: List of past content with performance metrics
            competitor_insights: Insights from competitor analysis
            
        Returns:
            Dict with strategy recommendations
        """
        if self.provider == "none":
            return {"note": "LLM disabled - using rule-based strategy"}
        
        system_prompt = """You are a social media strategist specializing in food content growth.
Analyze the provided data and give specific, actionable recommendations.
Be concise and data-driven."""

        # Format content history for prompt
        history_text = json.dumps(content_history[:10], indent=2)
        competitor_text = json.dumps(competitor_insights, indent=2)
        
        user_prompt = f"""Analyze this Instagram food account data and provide strategy:

CONTENT HISTORY (last 10 posts):
{history_text}

COMPETITOR INSIGHTS:
{competitor_text}

Provide recommendations in this format:
1. Top performing content type
2. Best posting times
3. Hashtag strategy
4. Content gaps to fill
5. 3 specific actions for next week

Response:"""

        try:
            response = self._call_llm(system_prompt, user_prompt, max_tokens=1200, timeout=60)
            return {"analysis": response, "source": "llm"}
        except Exception as e:
            logger.error(f"LLM strategy analysis failed: {e}")
            return {"error": str(e)}
    
    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: Any,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        """
        Call the configured LLM provider.
        
        Args:
            system_prompt: System/instruction prompt
            user_prompt: User query prompt
            
        Returns:
            LLM response text
        """
        if self.provider == "fireworks":
            return self._call_fireworks(
                system_prompt,
                user_prompt,
                max_tokens=max_tokens,
                timeout=timeout,
                json_mode=json_mode,
            )
        elif self.provider == "openai":
            return self._call_openai(system_prompt, user_prompt, max_tokens=max_tokens)
        else:
            raise LLMError(f"Provider {self.provider} not implemented")
    
    def _call_fireworks(
        self,
        system_prompt: str,
        user_prompt: Any,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        """Call Fireworks AI API (Kimi K2.5)"""
        url = f"{config.FIREWORKS_BASE_URL}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {config.FIREWORKS_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": config.FIREWORKS_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": config.LLM_TEMPERATURE,
            # Fireworks rejects non-streaming chat requests above 4096 output tokens.
            "max_tokens": min(max_tokens or config.LLM_MAX_TOKENS, 4096),
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        
        try:
            # Use persistent session for connection reuse (P1 improvement)
            session = self.get_session()
            response = session.post(url, headers=headers, json=payload, timeout=timeout or 45)
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except requests.exceptions.RequestException as e:
            logger.error(f"Fireworks API error: {e}")
            raise LLMError(f"Fireworks API call failed: {e}")
        except (KeyError, IndexError) as e:
            logger.error(f"Fireworks response parsing error: {e}")
            raise LLMError("Invalid response from Fireworks API")
    
    def _call_openai(
        self,
        system_prompt: str,
        user_prompt: Any,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Call OpenAI API"""
        try:
            import openai
            openai.api_key = config.OPENAI_API_KEY
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=config.LLM_TEMPERATURE,
                max_tokens=max_tokens or config.LLM_MAX_TOKENS
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise LLMError(f"OpenAI API call failed: {e}")

    def _build_post_recommendation_prompt(
        self,
        filepath: str,
        user_caption: Optional[str],
        context: Optional[str],
        fallback_analysis: Optional[Dict[str, Any]],
        visual_analysis: Optional[Dict[str, Any]] = None,
    ) -> str:
        # Compact JSON encoding to reduce token count
        fallback_text = json.dumps(fallback_analysis or {}, ensure_ascii=True, separators=(',', ':'))
        visual_text = json.dumps(visual_analysis or {}, ensure_ascii=True, separators=(',', ':'))
        
        return f"""Analyze this Instagram asset for growth.

Asset: {Path(filepath).name}
Caption: {user_caption or 'none'}
Context: {context or 'none'}
Visual: {visual_text}
Fallback: {fallback_text}

Rules:
- Trust visual over text if they conflict
- Match posting time to meal type (breakfast→morning, etc.)
- Two caption variants: "Performance" (hook-first) and "Story-led" (brand voice)
- Two hashtag variants: "Broader Discovery" vs "Targeted Intent"
- Lower confidence if asset is ambiguous

Return JSON:
{{"content_analysis":{{"category":"...","dish_detected":"...","meal_type":"...","cuisine_type":"...","format":"image|video","confidence":0.0}},"caption_variants":[{{"label":"Performance","caption":"...","why":"..."}},{{"label":"Story-led","caption":"...","why":"..."}}],"hashtag_variants":[{{"label":"Broader Discovery","hashtags":["..."],"why":"..."}},{{"label":"Targeted Intent","hashtags":["..."],"why":"..."}}],"optimal_time":{{"time":"HH:MM","reasoning":"...","timezone":"local","engagement_prediction":"low|medium|high"}},"strategy_notes":"...","confidence_score":0.0,"content_patterns":["..."]}}"""

    def _inspect_visual_asset(
        self,
        filepath: str,
        user_caption: Optional[str],
        context: Optional[str],
    ) -> Dict[str, Any]:
        """Run a compact vision pass to understand the uploaded image before strategy generation.
        
        P1: Cached by file hash - repeated analysis of same file skips vision call.
        CRITICAL: Cache only stores visual facts. Text-dependent fields recomputed fresh.
        """
        user_text = f"{user_caption or ''} {context or ''}".strip()
        
        # Check cache first (P1 improvement)
        # Pass user_text so mismatch can be recomputed fresh (not cached)
        cached = self._get_cached_visual_analysis(filepath, user_text=user_text)
        if cached is not None:
            return cached
        
        image_data_url = self._build_image_data_url(filepath)
        if not image_data_url:
            return {
                "food_present": None,
                "primary_subject": "",
                "visual_summary": "",
                "dish_detected": "",
                "meal_type": "unknown",
                "cuisine_type": "",
                "format": "video" if Path(filepath).suffix.lower() in {".mov", ".mp4", ".m4v", ".avi"} else "image",
                "confidence": 0.2,
                "contradicts_user_text": False,
                "mismatch_note": "No direct image analysis available for this asset type.",
            }

        user_text = f"{user_caption or ''} {context or ''}".strip()
        content_blocks = [
            {
                "type": "text",
                "text": (
                    "Look at this uploaded image and identify what is actually visible. "
                    "Respond with exactly these 8 lines and nothing else:\n"
                    "FOOD_PRESENT=yes|no\n"
                    "PRIMARY_SUBJECT=...\n"
                    "DISH=...\n"
                    "MEAL_TYPE=breakfast|brunch|lunch|dinner|dessert/snack|beverage|unknown\n"
                    "CUISINE=...\n"
                    "CONFIDENCE=0.0-1.0\n"
                    "MISMATCH=yes|no\n"
                    "SUMMARY=...\n"
                    f"User-provided text to compare against: {user_text or 'none'}"
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": image_data_url},
            },
        ]
        system_prompt = (
            "You are a precise visual analyst. "
            "Report what is actually visible in the image. "
            "If the image is not food-related, say so directly. "
            "Do not explain your reasoning. Return only the requested 8 tagged lines."
        )
        # 8 tagged lines output ~80 tokens, 150 gives safe margin
        response = self._call_llm(system_prompt, content_blocks, max_tokens=150, timeout=45)
        result = self._parse_visual_analysis(response, filepath)

        # NOTE: Second visual-detail pass REMOVED from live request path
        # This was adding a serial remote round trip that doesn't justify the latency cost.
        # The _inspect_visual_detail method is kept for potential future debug/deep-analysis mode.
        # Previously triggered when: food_present=True and confidence >= 0.7

        # Cache successful visual analysis result (P1 improvement)
        self._cache_visual_analysis(filepath, result)
        
        return result

    def _inspect_visual_detail(
        self, image_data_url: str, first_pass: Dict[str, Any]
    ) -> Optional[str]:
        """Second vision pass: richer description for high-confidence food assets.
        
        NOTE: This is NOT called in the standard request path. It is kept for:
        1. Potential future debug/deep-analysis mode
        2. Manual enrichment workflows
        3. A/B testing visual description quality vs latency
        
        The standard path intentionally does NOT call this to maintain the 2-call max guarantee.
        """
        dish = first_pass.get("dish_detected") or "the dish"
        content_blocks = [
            {
                "type": "text",
                "text": (
                    f"You identified this as {dish}. "
                    "In 2-3 sentences describe: plating style, visible textures, "
                    "preparation cues (grilled, fried, garnished, etc.), freshness signals, "
                    "and the strongest appetite appeal in this frame. Be specific and visual."
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": image_data_url},
            },
        ]
        try:
            return self._call_llm(
                "You are a food photography critic. Be specific and visual.",
                content_blocks,
                max_tokens=180,
                timeout=30,
            ).strip()
        except Exception:
            return None

    def _parse_visual_analysis(self, text: str, filepath: str) -> Dict[str, Any]:
        """Parse tagged-line visual analysis output into a structured dict."""
        parsed: Dict[str, str] = {}
        for line in text.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            parsed[key.strip().upper()] = value.strip()

        food_flag = parsed.get("FOOD_PRESENT", "").lower()
        food_present: Optional[bool]
        if food_flag == "yes":
            food_present = True
        elif food_flag == "no":
            food_present = False
        else:
            food_present = None

        mismatch_flag = parsed.get("MISMATCH", "").lower()
        mismatch = True if mismatch_flag == "yes" else False
        confidence_raw = parsed.get("CONFIDENCE", "0.3")
        try:
            confidence = max(0.0, min(float(confidence_raw), 1.0))
        except ValueError:
            confidence = 0.3

        return {
            "food_present": food_present,
            "primary_subject": parsed.get("PRIMARY_SUBJECT", ""),
            "visual_summary": parsed.get("SUMMARY", ""),
            "dish_detected": parsed.get("DISH", ""),
            "meal_type": parsed.get("MEAL_TYPE", "unknown").lower() or "unknown",
            "cuisine_type": parsed.get("CUISINE", ""),
            "format": "video" if Path(filepath).suffix.lower() in {".mov", ".mp4", ".m4v", ".avi"} else "image",
            "confidence": confidence,
            "contradicts_user_text": mismatch,
            "mismatch_note": parsed.get("SUMMARY", ""),
        }

    def _build_image_data_url(self, filepath: str) -> Optional[str]:
        """Load an image file and return a JPEG data URL suitable for multimodal requests.
        
        P1: Timing is captured in _prepare_visual_analysis_image for preprocessing,
        and additional timing here for base64 encoding.
        """
        import time
        start_time = time.perf_counter()
        
        prepared_image = self._prepare_visual_analysis_image(filepath)
        if not prepared_image:
            return None

        try:
            with Image.open(prepared_image) as img:
                img = ImageOps.exif_transpose(img)
                if max(img.size) > 1600:
                    img.thumbnail((1600, 1600))
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                elif img.mode == "L":
                    img = img.convert("RGB")

                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=88, optimize=True)
                payload = buffer.getvalue()

                if len(payload) > 7_500_000:
                    img.thumbnail((1280, 1280))
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=78, optimize=True)
                    payload = buffer.getvalue()

                if len(payload) > 9_500_000:
                    raise LLMError("Image is too large for Fireworks vision request")

                encoded = base64.b64encode(payload).decode("utf-8")
                result = f"data:image/jpeg;base64,{encoded}"
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.info(f"Image data URL built for {Path(filepath).name} ({elapsed_ms:.1f}ms)")
                return result
        except (FileNotFoundError, UnidentifiedImageError, OSError) as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(f"Image preprocessing failed for {filepath} ({elapsed_ms:.1f}ms): {exc}")
            return None

    def _prepare_visual_analysis_image(self, filepath: str) -> Optional[Path]:
        """Return a normalized JPEG path for image/video analysis.
        
        P1: Caches normalized artifacts in .analysis-cache directory.
        Reuses cached version if source mtime hasn't changed.
        """
        import time
        start_time = time.perf_counter()
        
        source_path = Path(filepath)
        suffix = source_path.suffix.lower()
        cache_dir = source_path.parent / ".analysis-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        normalized_path = cache_dir / f"{source_path.stem}.analysis.jpg"

        # Check for cached normalized artifact (P1: deterministic and lightweight)
        if normalized_path.exists() and normalized_path.stat().st_mtime >= source_path.stat().st_mtime:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"Media preprocessing CACHE HIT for {source_path.name} ({elapsed_ms:.1f}ms)")
            return normalized_path

        # Need to create normalized artifact
        result = None
        if suffix in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".ppm", ".webp", ".heic", ".heif"}:
            result = self._normalize_image_file(source_path, normalized_path)
        elif suffix in {".mov", ".mp4", ".m4v", ".avi"}:
            result = self._extract_video_frame(source_path, normalized_path)
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        cache_status = "CREATED" if result else "FAILED"
        logger.info(f"Media preprocessing {cache_status} for {source_path.name} ({elapsed_ms:.1f}ms)")
        
        return result

    def _normalize_image_file(self, source_path: Path, output_path: Path) -> Optional[Path]:
        """Normalize an image into a JPEG that can be sent to the vision model."""
        try:
            with Image.open(source_path) as img:
                img = ImageOps.exif_transpose(img)
                if max(img.size) > 2048:
                    img.thumbnail((2048, 2048))
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                elif img.mode == "L":
                    img = img.convert("RGB")
                img.save(output_path, format="JPEG", quality=90, optimize=True)
                return output_path
        except (FileNotFoundError, UnidentifiedImageError, OSError) as exc:
            heif_note = " (HEIF support unavailable)" if source_path.suffix.lower() in {".heic", ".heif"} and not HEIF_AVAILABLE else ""
            logger.warning(f"Image normalization failed for {source_path}{heif_note}: {exc}")
            return None

    def _extract_video_frame(self, source_path: Path, output_path: Path) -> Optional[Path]:
        """Extract a representative frame from a video for visual analysis."""
        if not VIDEO_FRAME_EXTRACTION_AVAILABLE:
            logger.warning(f"Video frame extraction unavailable for {source_path}: imageio-ffmpeg not installed")
            return None

        try:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            subprocess.run(
                [
                    ffmpeg_exe,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(source_path),
                    "-vf",
                    "thumbnail,scale=1280:-2",
                    "-frames:v",
                    "1",
                    str(output_path),
                ],
                check=True,
                timeout=45,
            )
            return output_path if output_path.exists() else None
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            logger.warning(f"Video frame extraction failed for {source_path}: {exc}")
            return None

    def _extract_json_object(self, text: str) -> Dict[str, Any]:
        """Extract a JSON object from a raw model response."""
        cleaned = text.strip()
        # Strip markdown code fences without corrupting JSON content
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = lines[1:]  # remove opening fence line (e.g. "```" or "```json")
            while lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise LLMError("No JSON object found in model response")
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError as exc:
                raise LLMError(f"Failed to parse recommendation JSON: {exc}") from exc

    def _extract_json_string_field(self, text: str, field_name: str) -> str:
        """Extract a non-empty string field from a JSON object response."""
        parsed = self._extract_json_object(text)
        value = parsed.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise LLMError(f"Missing or invalid '{field_name}' field in JSON response")
        return value.strip()

    def _extract_json_string_list_field(self, text: str, field_name: str, count: int) -> List[str]:
        """Extract a list of hashtag-style strings from a JSON object response."""
        parsed = self._extract_json_object(text)
        value = parsed.get(field_name)
        if not isinstance(value, list):
            raise LLMError(f"Missing or invalid '{field_name}' field in JSON response")

        cleaned: List[str] = []
        for item in value:
            tag = str(item).strip().lstrip("#")
            if not tag:
                continue
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_]{1,40}", tag):
                continue
            cleaned.append(tag)

        cleaned = list(dict.fromkeys(cleaned))
        if len(cleaned) < min(5, count):
            raise LLMError(f"Insufficient valid '{field_name}' values in JSON response")
        return cleaned[:count]

    def _validate_recommendation_payload(self, payload: Dict[str, Any]) -> None:
        """Validate core structured recommendation fields before they reach the analyzer."""
        if not isinstance(payload, dict):
            raise LLMError("Structured recommendation payload must be a JSON object")

        content_analysis = payload.get("content_analysis")
        if not isinstance(content_analysis, dict):
            raise LLMError("Structured recommendation missing content_analysis object")

        meal_type = str(content_analysis.get("meal_type") or "").strip().lower()
        if meal_type and meal_type not in VALID_MEAL_TYPES:
            raise LLMError(f"Invalid meal_type in structured recommendation: {meal_type}")

        for confidence_key in ("confidence_score",):
            raw_value = payload.get(confidence_key)
            if raw_value is None:
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise LLMError(f"Invalid {confidence_key} in structured recommendation") from exc
            if value < 0.0 or value > 1.0:
                raise LLMError(f"{confidence_key} out of range in structured recommendation")

        optimal_time = payload.get("optimal_time")
        if optimal_time is not None and not isinstance(optimal_time, dict):
            raise LLMError("Structured recommendation optimal_time must be an object")

    def _sanitize_caption_response(self, text: str) -> Optional[str]:
        """Return a usable caption or None if the model produced planning/meta output."""
        cleaned = text.strip().strip('"').strip("'")
        if not cleaned:
            return None

        meta_markers = [
            "the user wants",
            "requirements:",
            "strategy:",
            "draft ideas:",
            "let me",
            "option 1",
            "option 2",
            "word count",
        ]
        lower = cleaned.lower()
        if any(marker in lower for marker in meta_markers):
            quoted = re.findall(r'"([^"\n]{20,220})"', cleaned)
            if quoted:
                return quoted[-1].strip()
            return None

        lines = [line.strip(" -") for line in cleaned.splitlines() if line.strip()]
        for line in reversed(lines):
            if len(line.split()) <= 120 and ":" not in line[:25]:
                return line.strip('"').strip("'")

        return cleaned if len(cleaned.split()) <= 120 else None

    def _sanitize_hashtag_response(self, text: str, count: int) -> List[str]:
        """Extract a clean hashtag list from a noisy model response."""
        cleaned = text.strip()
        if not cleaned:
            return []

        tags: List[str] = []
        hashtag_matches = re.findall(r"#?([A-Za-z0-9][A-Za-z0-9_]{1,40})", cleaned)
        stopwords = {
            "the", "user", "wants", "requirements", "strategy", "wait", "count",
            "high", "volume", "niche", "community", "brand", "trending", "format",
            "comma", "separated", "symbol", "total", "discovery", "targeted", "reach",
        }
        for candidate in hashtag_matches:
            tag = candidate.strip().lstrip("#").lower()
            if len(tag) < 2 or tag in stopwords:
                continue
            if any(ch in tag for ch in ['"', "'", ".", ":", ";", "/"]):
                continue
            tags.append(tag)

        deduped = list(dict.fromkeys(tags))
        if len(deduped) >= min(8, count):
            return deduped[:count]
        return []
    
    def _template_caption(
        self,
        content_description: str,
        content_type: str,
        cuisine: Optional[str]
    ) -> str:
        """Fallback template-based caption generation"""
        import random
        
        templates = [
            "This {dish} is what comfort food dreams are made of 🥘✨ Who's craving this right now? 👇",
            "Homemade {dish} hits different on {day} 🍽️ What's your go-to comfort meal?",
            "The secret to the perfect {dish}? Patience and lots of love 💕 Save this recipe! 📌",
            "Weeknight {dish} done right in 30 minutes ⏰ Tag someone who needs this in their life 👇",
            "Channeling my {relative} with this {dish} recipe 🏠 Some flavors just taste like home 💭",
        ]
        
        template = random.choice(templates)
        return template.format(
            dish=content_description.split()[0] if content_description else "dish",
            day=datetime.now().strftime("%A"),
            relative=random.choice(["grandmother", "mother", "aunt"])
        )
    
    def _template_hashtags(
        self,
        content_type: str,
        cuisine: Optional[str],
        count: int
    ) -> List[str]:
        """Fallback template-based hashtag generation"""
        base_tags = [
            "food", "foodie", "instafood", "foodphotography", "homecooking",
            "recipe", "homemade", "cooking", "foodstagram", "delicious",
            "yummy", "foodblogger", "comfortfood", "easyrecipes", "weeknightdinner"
        ]
        
        if cuisine:
            base_tags.extend([f"{cuisine}food", f"{cuisine}cuisine", cuisine])
        
        if content_type == "breakfast":
            base_tags.extend(["breakfast", "brunch", "morningfuel"])
        elif content_type == "dessert":
            base_tags.extend(["dessert", "sweettooth", "baking"])
        
        return base_tags[:count]


# Convenience functions for direct use

def generate_caption(content_description: str, **kwargs) -> str:
    """Generate caption using configured LLM"""
    try:
        client = LLMClient()
        return client.generate_caption(content_description, **kwargs)
    except LLMError as e:
        logger.warning(f"LLM not available, using templates: {e}")
        client = LLMClient(provider="none")
        return client.generate_caption(content_description, **kwargs)


def generate_hashtags(content_description: str, **kwargs) -> List[str]:
    """Generate hashtags using configured LLM"""
    try:
        client = LLMClient()
        return client.generate_hashtags(content_description, **kwargs)
    except LLMError as e:
        logger.warning(f"LLM not available, using templates: {e}")
        client = LLMClient(provider="none")
        return client.generate_hashtags(content_description, **kwargs)


def generate_post_recommendation(filepath: str, **kwargs) -> Dict[str, Any]:
    """Generate a structured growth recommendation using the configured LLM."""
    client = LLMClient()
    return client.generate_post_recommendation(filepath, **kwargs)


def generate_reel_recommendation(filepath: str, **kwargs) -> Dict[str, Any]:
    """Generate a structured growth recommendation for an Instagram Reel."""
    client = LLMClient()
    return client.generate_reel_recommendation(filepath, **kwargs)


def analyze_visual_asset(filepath: str, **kwargs) -> Dict[str, Any]:
    """Analyze an uploaded image and return parsed visual facts."""
    client = LLMClient()
    return client._inspect_visual_asset(filepath, kwargs.get("user_caption"), kwargs.get("context"))


# Import datetime at end to avoid circular import
from datetime import datetime
