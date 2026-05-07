"""
Shared Duration Solver for Reel Generation

Core principle: Duration-driven, not asset-count-driven.
- 30/45/60 are targets with a ±5s practical band
- Platform max is 60s (hard ceiling)
- Images can be held longer than videos via Ken Burns/pan/zoom effects

This module provides a single source of truth for duration calculations,
ensuring preflight and planner never disagree.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum


class DurationTarget(Enum):
    """Standard reel duration targets."""
    SHORT = 30
    MEDIUM = 45
    LONG = 60


@dataclass
class CapacityResult:
    """Result from the shared duration solver."""
    feasible: bool
    requested_target: int  # 30/45/60 or custom
    feasible_target: int   # What can actually be achieved
    uploaded_count: int
    usable_count: int
    max_achievable: float  # Theoretical maximum with stretching
    recommended_target: int  # What the UI should suggest
    warnings: List[str]
    strategy: Dict  # How to achieve the target (holds, effects, etc.)


@dataclass
class SegmentAllocation:
    """Duration budget allocation for a segment."""
    asset_index: int
    base_duration: float
    stretched_duration: float
    effect_strategy: str  # "hold", "ken_burns", "pan", "zoom", "normal"
    is_padding: bool  # CTA or filler segment


# Configuration constants
PLATFORM_MAX_DURATION = 60.0  # Instagram hard limit
TARGET_TOLERANCE = 5.0  # ±5s practical band
MIN_SEGMENT_DURATION = 2.0  # Absolute minimum per segment
MAX_VIDEO_SEGMENT = 10.0  # Videos can't stretch much (limited by footage)
MAX_IMAGE_SEGMENT = 15.0  # Images can stretch via effects
EPSILON = 0.5  # Floating point tolerance for validation

# Structure requirements (intro + 1-3 body + outro)
MIN_SEGMENTS_FOR_STRUCTURE = 3  # intro + at least 1 body + outro
MAX_SEGMENTS_FOR_STRUCTURE = 5  # intro + 3 body + outro


def calculate_content_capacity(assets: List[Dict]) -> Tuple[float, int, int, List[str]]:
    """
    Calculate raw content capacity from a set of assets.
    
    Returns:
        - max_achievable_duration: Theoretical maximum with stretching
        - uploaded_count: Total assets provided
        - usable_count: Assets that passed quality/orientation checks
        - warnings: List of advisory messages
    """
    warnings = []
    uploaded_count = len(assets)
    usable_count = 0
    total_stretchable_seconds = 0.0
    
    for asset in assets:
        analysis = asset.get("analysis_json") or asset.get("analysis", {})
        suitability = analysis.get("reel_suitability", {})
        advanced = analysis.get("advanced_analysis", {})
        
        # Skip disqualified assets entirely
        if suitability.get("disqualified", False):
            continue
        
        # For images, orientation is advisory only (can crop/zoom)
        # For videos, orientation matters more but still not a hard block
        orientation_fit = advanced.get("orientation_fit", 0.7)
        media_type = asset.get("media_type", "video")
        
        if media_type == "image":
            # Images are always usable - we can crop/zoom/pan
            if orientation_fit < 0.2:
                warnings.append(f"Image {asset.get('id', 'unknown')} is landscape but will use crop/zoom")
            usable_count += 1
            # Images can stretch to MAX_IMAGE_SEGMENT
            total_stretchable_seconds += MAX_IMAGE_SEGMENT
        else:
            # Videos: check usable_duration_seconds but don't hard-reject
            usable_duration = advanced.get("usable_duration_seconds") or 3.0
            if orientation_fit < 0.2:
                warnings.append(f"Video {asset.get('id', 'unknown')} has low orientation fit but will use crop")
            usable_count += 1
            # Videos can stretch up to max of usable or MAX_VIDEO_SEGMENT
            total_stretchable_seconds += max(usable_duration, MAX_VIDEO_SEGMENT)
    
    return total_stretchable_seconds, uploaded_count, usable_count, warnings


def solve_duration_target(
    assets: List[Dict],
    requested_target: Optional[int] = None,
    allow_auto_select: bool = True
) -> CapacityResult:
    """
    Shared duration solver - single source of truth for preflight AND planner.
    
    Args:
        assets: List of asset dicts with analysis
        requested_target: 30, 45, 60, or None for auto
        allow_auto_select: Whether to automatically pick best target
    
    Returns:
        CapacityResult with feasibility, recommendations, and strategy
    """
    # Calculate raw capacity
    max_achievable, uploaded_count, usable_count, warnings = calculate_content_capacity(assets)
    
    # Auto mode: pick the best target based on what we have
    if requested_target is None:
        if usable_count >= 5 and max_achievable >= 55:
            requested_target = 60
        elif usable_count >= 4 and max_achievable >= 40:
            requested_target = 45
        else:
            requested_target = 30
    
    # Validate requested target is one of our standards
    if requested_target not in [30, 45, 60]:
        requested_target = 30  # Default to shortest if invalid
    
    # Determine feasibility
    # We need at least MIN_SEGMENTS_FOR_STRUCTURE to build a proper reel
    if usable_count < MIN_SEGMENTS_FOR_STRUCTURE:
        return CapacityResult(
            feasible=False,
            requested_target=requested_target,
            feasible_target=30,
            uploaded_count=uploaded_count,
            usable_count=usable_count,
            max_achievable=max_achievable,
            recommended_target=30,
            warnings=warnings + [f"Need at least {MIN_SEGMENTS_FOR_STRUCTURE} usable assets, have {usable_count}"],
            strategy={"error": "insufficient_assets"}
        )
    
    # Check if we can hit the requested target (within tolerance)
    tolerance = TARGET_TOLERANCE if requested_target < 60 else 2.0  # Tighter tolerance for 60s
    
    if max_achievable >= requested_target - tolerance:
        # We can reach the target (or close enough)
        feasible = True
        feasible_target = requested_target
        recommended_target = requested_target
    else:
        # Can't reach target - find best fallback
        feasible = False
        if max_achievable >= 55:
            feasible_target = 60
            recommended_target = 60
        elif max_achievable >= 40:
            feasible_target = 45
            recommended_target = 45
        else:
            feasible_target = 30
            recommended_target = 30
    
    # Build strategy for achieving the target
    strategy = build_duration_strategy(assets, recommended_target, usable_count)
    
    return CapacityResult(
        feasible=feasible,
        requested_target=requested_target,
        feasible_target=feasible_target,
        uploaded_count=uploaded_count,
        usable_count=usable_count,
        max_achievable=max_achievable,
        recommended_target=recommended_target,
        warnings=warnings,
        strategy=strategy
    )


def build_duration_strategy(
    assets: List[Dict],
    target_duration: int,
    usable_count: int
) -> Dict:
    """
    Build a strategy for achieving the target duration.
    
    Returns dict with:
    - intro_duration: seconds for intro segment
    - body_segments: list of body segment allocations
    - outro_duration: seconds for outro/CTA segment
    - padding_strategy: how to fill any gap (holds, effects)
    - clamp_strategy: how to handle overshoot (trim, speed)
    """
    # Standard structure: intro + body + outro
    # Body segments = usable_count - 2 (intro + outro)
    # But cap at 3 body segments for pacing
    body_count = min(usable_count - 2, 3) if usable_count >= 4 else 1
    
    # Allocate duration budget
    # Intro: ~15-20% of target (but at least 5s)
    intro_duration = max(5.0, target_duration * 0.18)
    
    # Outro/CTA: ~10-15% (but at least 3s)
    outro_duration = max(3.0, target_duration * 0.12)
    
    # Body gets the rest
    body_budget = target_duration - intro_duration - outro_duration
    
    # Distribute body budget across segments
    base_body_duration = body_budget / body_count if body_count > 0 else body_budget
    
    body_allocations = []
    for i in range(body_count):
        # Slightly vary durations for pacing (not all identical)
        variation = 1.0 if i % 2 == 0 else -0.5  # Alternating longer/shorter
        segment_duration = base_body_duration + variation
        
        body_allocations.append({
            "index": i,
            "duration": segment_duration,
            "min_duration": MIN_SEGMENT_DURATION,
            "max_duration": MAX_IMAGE_SEGMENT,  # Can stretch to this
            "effect_strategy": "ken_burns" if i == 0 else "normal",  # First body gets Ken Burns
        })
    
    return {
        "target_duration": target_duration,
        "intro_duration": intro_duration,
        "outro_duration": outro_duration,
        "body_budget": body_budget,
        "body_count": body_count,
        "body_allocations": body_allocations,
        "padding_strategy": "extend_cta" if target_duration > 45 else "normal",
        "clamp_strategy": "trim_last_segment" if target_duration >= 55 else "normal",
        "tolerance_band": TARGET_TOLERANCE,
    }


def allocate_segment_durations(
    selected_assets: List[Dict],
    target_duration: int,
    strategy: Optional[Dict] = None
) -> List[SegmentAllocation]:
    """
    Allocate actual durations to segments based on the target.
    This is used by the planner to build the timeline.
    
    Returns list of SegmentAllocation with stretched durations.
    """
    if not selected_assets:
        return []
    
    if strategy is None:
        strategy = build_duration_strategy(selected_assets, target_duration, len(selected_assets))
    
    allocations = []
    
    # Intro segment (always first asset)
    allocations.append(SegmentAllocation(
        asset_index=0,
        base_duration=5.0,
        stretched_duration=strategy["intro_duration"],
        effect_strategy="fade_in",
        is_padding=False
    ))
    
    # Body segments
    body_allocations = strategy.get("body_allocations", [])
    for i, body in enumerate(body_allocations):
        if i + 1 < len(selected_assets):  # +1 because intro uses index 0
            asset = selected_assets[i + 1]
            media_type = asset.get("media_type", "video")
            
            # Determine max stretch based on media type
            if media_type == "image":
                max_stretch = MAX_IMAGE_SEGMENT
                effect = body.get("effect_strategy", "ken_burns")
            else:
                max_stretch = MAX_VIDEO_SEGMENT
                effect = "normal"
            
            target_segment = body["duration"]
            
            # Clamp to max stretch
            if target_segment > max_stretch:
                warnings.warn(f"Segment {i} capped at {max_stretch}s (was {target_segment}s)")
                target_segment = max_stretch
            
            allocations.append(SegmentAllocation(
                asset_index=i + 1,
                base_duration=3.0,
                stretched_duration=target_segment,
                effect_strategy=effect,
                is_padding=False
            ))
    
    # Outro/CTA segment (last asset)
    if len(selected_assets) > 1:
        allocations.append(SegmentAllocation(
            asset_index=len(selected_assets) - 1,
            base_duration=3.0,
            stretched_duration=strategy["outro_duration"],
            effect_strategy="hold" if target_duration > 45 else "normal",
            is_padding=False
        ))
    
    # Now balance the total to match target exactly
    current_total = sum(a.stretched_duration for a in allocations)
    difference = target_duration - current_total
    
    # If we're short, extend the outro/CTA and strongest images
    if difference > EPSILON:
        # First try to extend the outro
        for alloc in allocations:
            if alloc.effect_strategy == "hold":
                extension = min(difference, 5.0)  # Cap extension
                alloc.stretched_duration += extension
                difference -= extension
                if difference <= EPSILON:
                    break
        
        # Then extend image segments with effects
        if difference > EPSILON:
            for alloc in allocations:
                if alloc.effect_strategy in ["ken_burns", "pan", "zoom"]:
                    media_type = selected_assets[alloc.asset_index].get("media_type", "video")
                    max_for_type = MAX_IMAGE_SEGMENT if media_type == "image" else MAX_VIDEO_SEGMENT
                    headroom = max_for_type - alloc.stretched_duration
                    extension = min(difference, headroom, 3.0)  # Cap per extension
                    if extension > 0:
                        alloc.stretched_duration += extension
                        difference -= extension
                        if difference <= EPSILON:
                            break
    
    # If we're over, trim from the end
    elif difference < -EPSILON:
        # Trim from the last non-padding segment
        for alloc in reversed(allocations):
            if not alloc.is_padding:
                reduction = min(abs(difference), alloc.stretched_duration - MIN_SEGMENT_DURATION)
                if reduction > 0:
                    alloc.stretched_duration -= reduction
                    difference += reduction
                    if difference >= -EPSILON:
                        break
    
    return allocations


def validate_plan_against_target(
    plan_segments: List[Dict],
    target_duration: int,
    platform_max: float = PLATFORM_MAX_DURATION
) -> Tuple[bool, float, Optional[str]]:
    """
    Validate a plan against the target duration.
    
    Returns:
        - is_valid: bool
        - actual_duration: float
        - error_message: None if valid, otherwise explanation
    
    Uses ±5s tolerance band and clamps borderline cases.
    """
    actual_duration = sum(seg.get("duration_seconds", 0) for seg in plan_segments)
    
    # Check platform hard ceiling
    if actual_duration > platform_max + EPSILON:
        return False, actual_duration, f"Plan exceeds platform max: {actual_duration:.1f}s > {platform_max}s"
    
    # Check target band tolerance
    lower_bound = target_duration - TARGET_TOLERANCE
    upper_bound = target_duration + TARGET_TOLERANCE
    
    if actual_duration < lower_bound:
        return False, actual_duration, f"Plan too short: {actual_duration:.1f}s < {lower_bound}s target band"
    
    if actual_duration > upper_bound:
        # Over target band but under platform max - we can clamp
        return True, min(actual_duration, target_duration), None  # Valid but should clamp
    
    return True, actual_duration, None


def clamp_duration_to_target(
    segments: List[Dict],
    target_duration: int,
    platform_max: float = PLATFORM_MAX_DURATION
) -> List[Dict]:
    """
    Clamp segment durations to fit within target and platform constraints.
    
    Returns adjusted segments that honor:
    - Total ≈ target_duration (within tolerance)
    - Total ≤ platform_max
    - Each segment ≥ MIN_SEGMENT_DURATION
    """
    if not segments:
        return segments
    
    current_total = sum(seg.get("duration_seconds", 0) for seg in segments)
    
    # If already within target band, return as-is
    if abs(current_total - target_duration) <= TARGET_TOLERANCE:
        return segments
    
    # If over platform max, we must trim
    if current_total > platform_max:
        excess = current_total - platform_max
        # Trim from the end (last segments are less critical)
        for seg in reversed(segments):
            if excess <= 0:
                break
            current = seg.get("duration_seconds", 0)
            trim_amount = min(excess, current - MIN_SEGMENT_DURATION)
            if trim_amount > 0:
                seg["duration_seconds"] = current - trim_amount
                excess -= trim_amount
    
    # Re-calculate and clamp to target if still over
    current_total = sum(seg.get("duration_seconds", 0) for seg in segments)
    if current_total > target_duration + EPSILON:
        excess = current_total - target_duration
        for seg in reversed(segments):
            if excess <= EPSILON:
                break
            current = seg.get("duration_seconds", 0)
            trim_amount = min(excess, current - MIN_SEGMENT_DURATION)
            if trim_amount > EPSILON:
                seg["duration_seconds"] = current - trim_amount
                excess -= trim_amount
    
    return segments
