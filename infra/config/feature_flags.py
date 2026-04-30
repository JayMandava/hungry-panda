"""
Feature Flag System - Phase 5
Centralized feature flag management for gradual rollouts and A/B testing.
"""
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass

from infra.config.settings import config
from infra.config.logging_config import logger


class FeatureFlag(str, Enum):
    """Feature flags available in the system"""
    REMOTION_RENDERER = "remotion_renderer"
    REMOTION_PLAYER_PREVIEW = "remotion_player_preview"
    # Add more flags as needed


@dataclass
class FlagState:
    """State of a feature flag"""
    enabled: bool
    rollout_percentage: int  # 0-100
    target_users: Optional[list]  # User IDs for targeted rollout
    metadata: Dict[str, Any]


class FeatureFlagManager:
    """
    Manages feature flags for gradual rollouts.
    
    Priority (highest to lowest):
    1. Environment variable override
    2. Per-user targeting
    3. Percentage rollout
    4. Default from config
    """
    
    def __init__(self):
        self._flags: Dict[FeatureFlag, FlagState] = {}
        self._load_default_flags()
    
    def _load_default_flags(self):
        """Load default flag states from config"""
        self._flags = {
            FeatureFlag.REMOTION_RENDERER: FlagState(
                enabled=config.ENABLE_REMOTION_RENDERER,
                rollout_percentage=100 if config.ENABLE_REMOTION_RENDERER else 0,
                target_users=None,
                metadata={"description": "Use Remotion instead of FFmpeg for rendering"}
            ),
            FeatureFlag.REMOTION_PLAYER_PREVIEW: FlagState(
                enabled=False,  # Not yet implemented
                rollout_percentage=0,
                target_users=None,
                metadata={"description": "Use Remotion Player for interactive preview"}
            )
        }
    
    def is_enabled(
        self, 
        flag: FeatureFlag, 
        user_id: Optional[str] = None,
        force_check: bool = False
    ) -> bool:
        """
        Check if a feature flag is enabled.
        
        Args:
            flag: The feature flag to check
            user_id: Optional user ID for targeted rollout
            force_check: If True, ignore environment override
            
        Returns:
            True if feature is enabled for this context
        """
        state = self._flags.get(flag)
        if not state:
            return False
        
        # Environment variable override (unless force_check)
        if not force_check:
            env_override = self._get_env_override(flag)
            if env_override is not None:
                return env_override
        
        # Check if globally enabled
        if not state.enabled:
            return False
        
        # Check targeted users
        if user_id and state.target_users:
            if user_id in state.target_users:
                logger.debug(f"Feature {flag} enabled for targeted user {user_id}")
                return True
        
        # Check percentage rollout (if user_id provided)
        if user_id and state.rollout_percentage < 100:
            # Deterministic hash-based check
            import hashlib
            hash_val = int(hashlib.md5(f"{flag}:{user_id}".encode()).hexdigest(), 16)
            user_bucket = hash_val % 100
            enabled = user_bucket < state.rollout_percentage
            logger.debug(f"Feature {flag} {'enabled' if enabled else 'disabled'} for user {user_id} (bucket: {user_bucket})")
            return enabled
        
        return state.enabled
    
    def _get_env_override(self, flag: FeatureFlag) -> Optional[bool]:
        """Check for environment variable override"""
        env_map = {
            FeatureFlag.REMOTION_RENDERER: "ENABLE_REMOTION_RENDERER",
        }
        
        env_var = env_map.get(flag)
        if env_var:
            import os
            val = os.getenv(env_var)
            if val is not None:
                return val.lower() in ("true", "1", "yes", "on")
        
        return None
    
    def get_flag_state(self, flag: FeatureFlag) -> Optional[FlagState]:
        """Get full state of a flag"""
        return self._flags.get(flag)
    
    def update_flag(
        self, 
        flag: FeatureFlag, 
        enabled: bool,
        rollout_percentage: Optional[int] = None
    ):
        """Update flag state (for dynamic configuration)"""
        if flag in self._flags:
            state = self._flags[flag]
            state.enabled = enabled
            if rollout_percentage is not None:
                state.rollout_percentage = max(0, min(100, rollout_percentage))
            logger.info(f"Updated flag {flag}: enabled={enabled}, rollout={state.rollout_percentage}%")
    
    def get_all_flags(self) -> Dict[str, Any]:
        """Get status of all flags (for admin/debugging)"""
        return {
            flag.value: {
                "enabled": state.enabled,
                "rollout_percentage": state.rollout_percentage,
                "metadata": state.metadata
            }
            for flag, state in self._flags.items()
        }


# Global instance
feature_flags = FeatureFlagManager()


def is_remotion_enabled(user_id: Optional[str] = None) -> bool:
    """Convenience function for Remotion renderer flag"""
    return feature_flags.is_enabled(FeatureFlag.REMOTION_RENDERER, user_id)


def is_remotion_player_enabled(user_id: Optional[str] = None) -> bool:
    """Convenience function for Remotion Player flag"""
    return feature_flags.is_enabled(FeatureFlag.REMOTION_PLAYER_PREVIEW, user_id)
