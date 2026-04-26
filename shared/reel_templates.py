"""
Shared reel templates configuration.
This module contains templates to avoid circular imports between app.api.reels and workers.reels.
"""

# Templates available for reel creation
REEL_TEMPLATES = {
    "dish_showcase": {
        "name": "Dish Showcase",
        "description": "Highlight a signature dish with appetizing shots",
        "pacing": "medium",
        "transitions": "smooth",
        "version": "1.0"
    },
    "recipe_steps": {
        "name": "Recipe Steps",
        "description": "Show cooking process from ingredients to final plate",
        "pacing": "quick",
        "transitions": "cut",
        "version": "1.0"
    },
    "ambience_montage": {
        "name": "Ambience Montage",
        "description": "Atmospheric shots of your restaurant or kitchen",
        "pacing": "slow",
        "transitions": "fade",
        "version": "1.0"
    },
    "platter_reveal": {
        "name": "Platter Reveal",
        "description": "Build anticipation for a grand food presentation",
        "pacing": "dramatic",
        "transitions": "zoom",
        "version": "1.0"
    },
    "chef_special": {
        "name": "Chef's Special",
        "description": "Feature your chef preparing their signature creation",
        "pacing": "medium",
        "transitions": "smooth",
        "version": "1.0"
    },
    "ingredient_focus": {
        "name": "Ingredient Focus",
        "description": "Close-ups of fresh ingredients and textures",
        "pacing": "slow",
        "transitions": "fade",
        "version": "1.0"
    },
    "satisfying_sizzle": {
        "name": "Satisfying Sizzle",
        "description": "ASMR-style cooking sounds and visual satisfaction",
        "pacing": "quick",
        "transitions": "cut",
        "version": "1.0"
    },
    "behind_the_scenes": {
        "name": "Behind the Scenes",
        "description": "Kitchen action, prep work, and candid moments",
        "pacing": "medium",
        "transitions": "smooth",
        "version": "1.0"
    }
}

# Valid status values
PROJECT_STATUSES = ["draft", "queued", "analyzing", "plan_ready", "rendering", "ready", "failed", "published"]
RENDER_STATUSES = ["queued", "analyzing", "running", "plan_ready", "completed", "failed"]
PUBLISH_STATUSES = ["queued", "publishing", "published", "failed"]
