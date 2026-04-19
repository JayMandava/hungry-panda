"""
LLM Client for Hungry Panda
Supports multiple providers: Fireworks AI (Kimi K2.5), OpenAI
"""
import json
import logging
from typing import Dict, List, Optional, Any
import requests

from config.settings import config

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Custom exception for LLM errors"""
    pass


class LLMClient:
    """
    Unified LLM client supporting multiple providers.
    
    Primary: Fireworks AI (Kimi K2.5)
    Fallback: OpenAI
    """
    
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or config.LLM_PROVIDER
        self._validate_config()
    
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
        
        system_prompt = """You are a social media expert specializing in food and cooking content.
Your captions are engaging, authentic, and drive engagement (likes, comments, saves).
Keep captions concise (under 100 words), use emojis naturally, and include a hook.
Never use generic phrases like "delicious" or "yummy" without context."""

        user_prompt = f"""Create an Instagram caption for this {content_type} content:

Description: {content_description}
Cuisine: {cuisine or 'general'}
Tone: {tone}

Requirements:
- Start with a hook that stops the scroll
- Include 2-4 relevant emojis naturally
- Add a question or call-to-action at the end
- Keep it under 100 words
- Make it personal and authentic

Caption:"""

        try:
            response = self._call_llm(system_prompt, user_prompt)
            return response.strip()
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
        
        system_prompt = """You are a hashtag optimization expert for Instagram food content.
You understand which hashtags drive discovery vs engagement.
Provide hashtags without the # symbol, comma-separated."""

        user_prompt = f"""Generate {count} optimized Instagram hashtags for this food content:

Description: {content_description}
Type: {content_type}
Cuisine: {cuisine or 'general'}

Mix should include:
- 5-7 high-volume hashtags (100K+ posts) for discovery
- 8-10 niche hashtags (10K-100K) for targeted reach
- 3-5 community/brand hashtags
- 2-3 trending if applicable

Return only the hashtags, comma-separated, no # symbol:
"""

        try:
            response = self._call_llm(system_prompt, user_prompt)
            # Parse hashtags
            hashtags = [tag.strip().lstrip('#') for tag in response.split(',')]
            return hashtags[:count]
        except Exception as e:
            logger.error(f"LLM hashtag generation failed: {e}")
            return self._template_hashtags(content_type, cuisine, count)
    
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
            response = self._call_llm(system_prompt, user_prompt)
            return {"analysis": response, "source": "llm"}
        except Exception as e:
            logger.error(f"LLM strategy analysis failed: {e}")
            return {"error": str(e)}
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call the configured LLM provider.
        
        Args:
            system_prompt: System/instruction prompt
            user_prompt: User query prompt
            
        Returns:
            LLM response text
        """
        if self.provider == "fireworks":
            return self._call_fireworks(system_prompt, user_prompt)
        elif self.provider == "openai":
            return self._call_openai(system_prompt, user_prompt)
        else:
            raise LLMError(f"Provider {self.provider} not implemented")
    
    def _call_fireworks(self, system_prompt: str, user_prompt: str) -> str:
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
            "max_tokens": config.LLM_MAX_TOKENS
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except requests.exceptions.RequestException as e:
            logger.error(f"Fireworks API error: {e}")
            raise LLMError(f"Fireworks API call failed: {e}")
        except (KeyError, IndexError) as e:
            logger.error(f"Fireworks response parsing error: {e}")
            raise LLMError("Invalid response from Fireworks API")
    
    def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
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
                max_tokens=config.LLM_MAX_TOKENS
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise LLMError(f"OpenAI API call failed: {e}")
    
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


# Import datetime at end to avoid circular import
from datetime import datetime
