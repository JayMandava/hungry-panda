"""
Reels Maker - Phase 2: Analysis & Planning
Asset analysis, scoring, and edit plan generation
"""
import json
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from config.database import execute_insert, execute_query, DatabaseError
from config.logging_config import logger
from config.settings import config

# Import LLM client for visual analysis and edit planning
try:
    from integrations.llm_client import analyze_visual_asset, LLMClient
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    logger.warning("LLM client not available - visual analysis disabled")

# Global LLM client instance for reuse
_llm_client = None

def get_llm_client() -> Optional[LLMClient]:
    """Get or create LLM client instance"""
    global _llm_client
    if _llm_client is None and LLM_AVAILABLE:
        try:
            _llm_client = LLMClient()
        except Exception as e:
            logger.warning(f"Failed to initialize LLM client: {e}")
            return None
    return _llm_client


def analyze_reel_asset(asset_id: str, source_path: str, media_type: str) -> Dict[str, Any]:
    """
    Analyze a reel asset using existing visual analysis primitives.
    Returns structured facts and quality scores for reel suitability.
    """
    analysis = {
        "asset_id": asset_id,
        "media_type": media_type,
        "analyzed_at": datetime.utcnow().isoformat(),
        "visual_facts": {},
        "quality_scores": {},
        "reel_suitability": {}
    }
    
    try:
        # For images, run visual analysis
        if media_type == "image":
            if LLM_AVAILABLE:
                try:
                    visual_result = analyze_visual_asset(source_path)
                    analysis["visual_facts"] = {
                        "dish_detected": visual_result.get("dish_detected"),
                        "meal_type": visual_result.get("meal_type"),
                        "cuisine_type": visual_result.get("cuisine_type"),
                        "visual_summary": visual_result.get("visual_summary"),
                        "primary_subject": visual_result.get("primary_subject"),
                        "confidence": visual_result.get("confidence"),
                        "is_food_content": visual_result.get("is_food_content", True),
                        "contradicts_user_text": visual_result.get("contradicts_user_text", False)
                    }
                except Exception as e:
                    logger.warning(f"Visual analysis failed for {asset_id}: {e}")
                    analysis["visual_facts"] = {"error": str(e), "confidence": 0.5}
            else:
                # Heuristic fallback when LLM unavailable
                analysis["visual_facts"] = _heuristic_image_analysis(source_path)
        
        elif media_type == "video":
            # For videos: extract metadata AND analyze a representative frame
            metadata = _analyze_video_metadata(source_path)
            
            # Extract a frame for visual analysis (at 1 second mark)
            visual_analysis = _extract_and_analyze_video_frame(source_path, asset_id)
            
            # Merge metadata with visual analysis
            analysis["visual_facts"] = {
                **metadata,  # resolution, duration, frame_rate
                **visual_analysis,  # dish_detected, is_food_content, etc.
                "analysis_source": "video_frame"
            }
        
        # Score for reel suitability
        analysis["quality_scores"] = _score_asset_quality(analysis["visual_facts"], media_type)
        analysis["reel_suitability"] = _score_reel_suitability(analysis["visual_facts"], analysis["quality_scores"])
        
    except Exception as e:
        logger.error(f"Asset analysis failed for {asset_id}: {e}")
        analysis["error"] = str(e)
        analysis["quality_scores"] = {"overall": 0.5}  # Neutral score on error
        analysis["reel_suitability"] = {"role": "unknown", "score": 0.5}
    
    return analysis


def _heuristic_image_analysis(source_path: str) -> Dict[str, Any]:
    """Fallback heuristic analysis when LLM unavailable"""
    from PIL import Image
    
    try:
        with Image.open(source_path) as img:
            width, height = img.size
            aspect = width / height
            
            # Basic quality metrics
            resolution_score = min(1.0, (width * height) / (1080 * 1920))
            
            return {
                "resolution": f"{width}x{height}",
                "aspect_ratio": round(aspect, 2),
                "confidence": 0.5,
                "is_food_content": True,  # Assume food for heuristic
                "heuristic_analysis": True
            }
    except Exception as e:
        return {
            "error": str(e),
            "confidence": 0.3,
            "heuristic_analysis": True
        }


def _analyze_video_metadata(source_path: str) -> Dict[str, Any]:
    """Extract video metadata for analysis"""
    import subprocess
    
    try:
        # Use ffprobe to get video info
        result = subprocess.run(
            [
                'ffprobe', '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,duration,r_frame_rate',
                '-of', 'json',
                source_path
            ],
            capture_output=True,
            timeout=10
        )
        
        if result.returncode == 0:
            info = json.loads(result.stdout)
            stream = info.get('streams', [{}])[0]
            
            width = stream.get('width', 0)
            height = stream.get('height', 0)
            duration = float(stream.get('duration', 0))
            
            # Parse frame rate (e.g., "30/1" -> 30)
            fps_str = stream.get('r_frame_rate', '30/1')
            if '/' in fps_str:
                num, den = fps_str.split('/')
                fps = float(num) / float(den) if den != '0' else 30
            else:
                fps = float(fps_str)
            
            return {
                "resolution": f"{width}x{height}",
                "aspect_ratio": round(width / height, 2) if height else 1.0,
                "duration_seconds": round(duration, 1),
                "frame_rate": round(fps, 1),
                "confidence": 0.7,
                "is_food_content": True  # Assume food for now
            }
        else:
            return {
                "confidence": 0.3,
                "error": "ffprobe failed",
                "is_food_content": True
            }
    except FileNotFoundError:
        return {
            "confidence": 0.3,
            "error": "ffprobe not available",
            "is_food_content": True
        }
    except Exception as e:
        return {
            "confidence": 0.3,
            "error": str(e),
            "is_food_content": True
        }


def _extract_and_analyze_video_frame(source_path: str, asset_id: str, timestamp: float = 1.0) -> Dict[str, Any]:
    """
    Extract a representative frame from video and analyze it visually.
    Returns visual facts similar to image analysis.
    """
    import subprocess
    import tempfile
    from pathlib import Path
    
    temp_frame = None
    try:
        # Create temp file for extracted frame
        temp_dir = Path(tempfile.gettempdir())
        temp_frame = temp_dir / f"reel_frame_{asset_id}_{int(timestamp)}.jpg"
        
        # Extract frame using ffmpeg
        result = subprocess.run(
            [
                'ffmpeg', '-y',
                '-i', str(source_path),
                '-ss', str(timestamp),  # Seek to timestamp
                '-vframes', '1',  # Extract 1 frame
                '-q:v', '2',  # High quality
                str(temp_frame)
            ],
            capture_output=True,
            timeout=15
        )
        
        if result.returncode != 0:
            logger.warning(f"Failed to extract frame from {source_path}: {result.stderr.decode()[:200]}")
            return {
                "dish_detected": None,
                "visual_summary": "Frame extraction failed",
                "confidence": 0.3,
                "is_food_content": True,  # Assume food for fallback
                "frame_extraction_failed": True
            }
        
        if not temp_frame.exists():
            return {
                "dish_detected": None,
                "visual_summary": "Frame extraction failed",
                "confidence": 0.3,
                "is_food_content": True,
                "frame_extraction_failed": True
            }
        
        # Run visual analysis on extracted frame
        if LLM_AVAILABLE:
            try:
                visual_result = analyze_visual_asset(str(temp_frame))
                return {
                    "dish_detected": visual_result.get("dish_detected"),
                    "meal_type": visual_result.get("meal_type"),
                    "cuisine_type": visual_result.get("cuisine_type"),
                    "visual_summary": visual_result.get("visual_summary"),
                    "primary_subject": visual_result.get("primary_subject"),
                    "confidence": visual_result.get("confidence"),
                    "is_food_content": visual_result.get("is_food_content", True),
                    "contradicts_user_text": visual_result.get("contradicts_user_text", False),
                    "frame_timestamp": timestamp,
                    "analysis_source": "llm"
                }
            except Exception as e:
                logger.warning(f"Visual analysis failed for video frame {asset_id}: {e}")
                return {
                    "dish_detected": None,
                    "visual_summary": f"Visual analysis error: {str(e)[:100]}",
                    "confidence": 0.4,
                    "is_food_content": True,
                    "frame_timestamp": timestamp
                }
        else:
            # Heuristic fallback - use PIL to check image properties
            from PIL import Image
            with Image.open(temp_frame) as img:
                width, height = img.size
                return {
                    "resolution": f"{width}x{height}",
                    "confidence": 0.5,
                    "is_food_content": True,
                    "heuristic_analysis": True,
                    "frame_timestamp": timestamp,
                    "analysis_source": "heuristic"
                }
                
    except FileNotFoundError:
        return {
            "dish_detected": None,
            "visual_summary": "ffmpeg not available for frame extraction",
            "confidence": 0.3,
            "is_food_content": True,
            "frame_extraction_failed": True
        }
    except Exception as e:
        logger.error(f"Frame extraction/analysis failed for {asset_id}: {e}")
        return {
            "dish_detected": None,
            "visual_summary": f"Analysis error: {str(e)[:100]}",
            "confidence": 0.3,
            "is_food_content": True
        }
    finally:
        # Clean up temp file
        if temp_frame and temp_frame.exists():
            try:
                temp_frame.unlink()
            except:
                pass


def _score_asset_quality(visual_facts: Dict, media_type: str) -> Dict[str, float]:
    """Score visual quality of the asset"""
    scores = {
        "resolution": 0.7,
        "clarity": 0.7,
        "composition": 0.7,
        "lighting": 0.7,
        "overall": 0.7
    }
    
    # Adjust based on visual facts
    if media_type == "image":
        resolution = visual_facts.get("resolution", "")
        if resolution:
            try:
                w, h = map(int, resolution.lower().split('x'))
                # Score based on vertical resolution for 9:16 reels
                if h >= 1920:
                    scores["resolution"] = 1.0
                elif h >= 1080:
                    scores["resolution"] = 0.9
                elif h >= 720:
                    scores["resolution"] = 0.7
                else:
                    scores["resolution"] = 0.5
            except:
                pass
        
        # Confidence affects all scores
        confidence = visual_facts.get("confidence", 0.7)
        if confidence < 0.5:
            scores["clarity"] = 0.4
    
    elif media_type == "video":
        duration = visual_facts.get("duration_seconds", 0)
        # Shorter clips are better for reels
        if 3 <= duration <= 10:
            scores["composition"] = 0.9
        elif duration > 30:
            scores["composition"] = 0.5  # Too long
        
        # Resolution scoring for video
        resolution = visual_facts.get("resolution", "")
        if resolution:
            try:
                w, h = map(int, resolution.lower().split('x'))
                if h >= 1080:
                    scores["resolution"] = 0.9
                elif h >= 720:
                    scores["resolution"] = 0.7
            except:
                pass
    
    # Calculate overall
    scores["overall"] = sum(scores.values()) / len(scores)
    return scores


def _score_reel_suitability(visual_facts: Dict, quality_scores: Dict) -> Dict[str, Any]:
    """Score asset for specific reel roles (intro, body, outro)"""
    overall = quality_scores.get("overall", 0.7)
    
    # Determine best role
    role_scores = {
        "intro": overall * 0.9,   # Slightly penalized - need strong hook
        "body": overall,          # Standard
        "outro": overall * 0.95   # Slightly penalized - need CTA potential
    }
    
    # Boost intro score for high-confidence hero shots
    confidence = visual_facts.get("confidence", 0.7)
    is_food = visual_facts.get("is_food_content", True)
    dish = visual_facts.get("dish_detected")
    
    if confidence > 0.8 and is_food and dish:
        role_scores["intro"] = overall * 1.1  # Good hook potential
    
    # Determine best role
    best_role = max(role_scores, key=role_scores.get)
    
    return {
        "role": best_role,
        "role_scores": role_scores,
        "score": role_scores[best_role],
        "recommended": role_scores[best_role] >= 0.6
    }


def select_assets_for_reel(assets: List[Dict], target_duration: int = 30) -> List[Dict]:
    """
    Select and rank assets for reel inclusion.
    PRESERVES STRICT UPLOAD ORDER - does not reorder by score.
    Returns ordered list of selected assets with their roles.
    """
    if not assets:
        return []
    
    # Sort by upload order (sort_order) - strict preservation
    sorted_assets = sorted(assets, key=lambda x: x.get("sort_order", 0))
    
    # Filter to recommended assets only (but keep upload order)
    recommended = [
        a for a in sorted_assets
        if a.get("analysis_json", {}).get("reel_suitability", {}).get("recommended", True)
    ]
    
    if not recommended:
        # Fall back to all assets if none recommended (still in upload order)
        recommended = sorted_assets
    
    # Assign roles based on upload order position (not by score)
    selected = []
    for idx, asset in enumerate(recommended[:8]):  # Max 8 assets
        # Get score for reference (but don't use it for ordering)
        score = asset.get("analysis_json", {}).get("reel_suitability", {}).get("score", 0.5)
        
        # Assign roles based on position in upload sequence
        role = "body"
        if idx == 0:
            role = "intro"  # First uploaded asset is intro
        elif idx >= len(recommended) - 2 and len(recommended) > 2:
            role = "outro"  # Last 1-2 assets are outro
        
        selected.append({
            "asset_id": asset["id"],
            "source_path": asset["source_path"],
            "media_type": asset["media_type"],
            "sort_order": asset.get("sort_order", idx),
            "role": role,
            "score": score,  # Kept for reference only
            "analysis": asset.get("analysis_json", {})
        })
    
    return selected


def _generate_ai_edit_plan_prompt(selected_assets: List[Dict], template_key: str, template: Dict, target_duration: int) -> str:
    """Generate a prompt for AI to create edit plan decisions"""
    
    # Build asset descriptions
    asset_descriptions = []
    for idx, asset in enumerate(selected_assets):
        analysis = asset.get("analysis", {})
        visual = analysis.get("visual_facts", {})
        
        desc = f"Asset {idx+1}: {asset['media_type']}"
        if visual.get("dish_detected"):
            desc += f" showing {visual['dish_detected']}"
        if visual.get("visual_summary"):
            desc += f" - {visual['visual_summary'][:100]}"
        desc += f" (role: {asset['role']}, confidence: {visual.get('confidence', 0.5):.2f})"
        asset_descriptions.append(desc)
    
    prompt = f"""You are a professional video editor creating an Instagram Reel edit plan.

TEMPLATE: {template_key}
Template style: {template.get('name', 'Custom')}
Description: {template.get('description', '')}
Pacing: {template.get('pacing', 'medium')}
Transitions: {template.get('transitions', 'smooth')}
Target duration: {target_duration} seconds

ASSETS ({len(selected_assets)} total):
{chr(10).join(asset_descriptions)}

Create an engaging edit plan. For EACH asset, provide:
1. Duration (in seconds) - consider pacing and content type
2. Transition to NEXT segment (fade_in, crossfade, hard_cut, fade, zoom)
3. Overlay text hook/CTA if appropriate (keep short, punchy)
4. Effect notes (e.g., "Ken Burns zoom", "quick cut", "hold for reveal")

Think about:
- First asset needs a strong hook to grab attention
- Middle assets should maintain energy
- Last asset should have clear CTA or satisfying conclusion
- Match transitions to template style ({template.get('transitions', 'smooth')})
- Total must fit within {target_duration}s

Return your decisions as structured data."""

    return prompt

def _parse_ai_edit_decisions(ai_response: str, selected_assets: List[Dict], base_durations: List[float]) -> List[Dict]:
    """Parse AI response into edit decisions, with fallback to base durations"""
    decisions = []
    
    # Try to extract structured data from AI response
    # Look for patterns like "Asset 1: X seconds", "duration: X", etc.
    import re
    
    for idx, asset in enumerate(selected_assets):
        # Default to base duration
        base_duration = base_durations[idx] if idx < len(base_durations) else 3.0
        
        # Try to find AI-specified duration for this asset
        duration = base_duration
        
        # Look for patterns in the AI response for this asset
        asset_section = re.search(
            rf'(?i)(asset\s*{idx+1}[^\\n]{{0,100}}|segment\s*{idx+1}[^\\n]{{0,100}})(.*?)(?=asset\s*{idx+2}|segment\s*{idx+2}|$)',
            ai_response + " Asset 999",  # Add terminator for last asset
            re.DOTALL
        )
        
        if asset_section:
            section = asset_section.group(2)
            # Look for duration hints
            duration_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:second|sec|s)\b', section, re.IGNORECASE)
            if duration_match:
                try:
                    parsed_duration = float(duration_match.group(1))
                    if 1.0 <= parsed_duration <= 10.0:  # Sanity check
                        duration = parsed_duration
                except:
                    pass
        
        decisions.append({
            "duration": duration,
            "ai_notes": asset_section.group(2)[:200] if asset_section else ""
        })
    
    return decisions


def _get_video_source_duration(asset: Dict[str, Any]) -> Optional[float]:
    """Return analyzed source duration for a video asset when available."""
    if asset.get("media_type") != "video":
        return None

    analysis = asset.get("analysis", {})
    visual = analysis.get("visual_facts", {})
    raw_duration = visual.get("duration_seconds")
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError):
        return None
    return duration if duration > 0 else None


def _clamp_segment_duration(
    asset: Dict[str, Any],
    requested_duration: float,
    selected_assets_count: int,
    target_duration: int,
) -> float:
    """Clamp a segment duration to sane bounds while respecting long source videos."""
    duration = max(1.0, float(requested_duration))
    video_source_duration = _get_video_source_duration(asset)

    if asset.get("media_type") != "video":
        return min(duration, float(target_duration))

    # Single long videos should produce a real reel-length segment, not a token 2s clip.
    if selected_assets_count == 1 and video_source_duration:
        duration = max(duration, min(video_source_duration, float(target_duration)))
    elif video_source_duration:
        duration = min(duration, video_source_duration)

    return min(duration, float(target_duration))


def _ensure_minimum_reel_duration(
    segments: List[Dict[str, Any]],
    selected_assets: List[Dict[str, Any]],
    target_duration: int,
    minimum_duration: float = 30.0,
) -> None:
    """
    Stretch ALL segments when the plan is too short to reach minimum 30s for Instagram.
    Extends segments proportionally - images can extend freely, videos capped by source duration.
    """
    current_total = sum(segment["duration"] for segment in segments)
    if current_total >= minimum_duration or not segments:
        return

    remaining_budget = float(target_duration) - current_total
    if remaining_budget <= 0:
        return

    required_extension = minimum_duration - current_total
    extension_budget = min(required_extension, remaining_budget)
    
    # Calculate how much each segment CAN be extended
    extendable_room = []  # (segment_idx, current_duration, max_extendable)
    total_extendable = 0.0
    
    for i, segment in enumerate(segments):
        if i >= len(selected_assets):
            break
        asset = selected_assets[i]
        current_dur = segment["duration"]
        
        if asset.get("media_type") == "video":
            # Videos capped by source duration
            source_duration = _get_video_source_duration(asset)
            if source_duration is not None:
                max_for_video = max(0.0, source_duration - current_dur)
                extendable_room.append((i, current_dur, max_for_video))
                total_extendable += max_for_video
            else:
                # Unknown source, allow some extension
                extendable_room.append((i, current_dur, 5.0))
                total_extendable += 5.0
        else:
            # Images can extend arbitrarily (Ken Burns can run longer)
            # But set a reasonable max per image to avoid excessive still time
            max_for_image = 15.0  # Allow images to stretch up to 15s each
            extendable_room.append((i, current_dur, max_for_image))
            total_extendable += max_for_image
    
    if total_extendable <= 0:
        return  # Nothing can be extended
    
    # Distribute extension proportionally
    extension_ratio = min(1.0, extension_budget / total_extendable)
    
    for seg_idx, current_dur, max_extendable in extendable_room:
        extension = max_extendable * extension_ratio
        if extension > 0.1:  # Only apply meaningful extensions
            segments[seg_idx]["duration"] = round(current_dur + extension, 2)
    
    # Verify we reached minimum - if not, try one more aggressive pass
    final_total = sum(s["duration"] for s in segments)
    if final_total < minimum_duration and total_extendable > 0:
        # Aggressive pass: use all remaining room
        remaining_needed = minimum_duration - final_total
        for seg_idx, current_dur, max_extendable in extendable_room:
            current_extended = segments[seg_idx]["duration"]
            already_added = current_extended - current_dur
            remaining_room = max_extendable - already_added
            if remaining_room > 0:
                extra = min(remaining_room, remaining_needed)
                segments[seg_idx]["duration"] = round(current_extended + extra, 2)
                remaining_needed -= extra
                if remaining_needed <= 0:
                    break

def generate_edit_plan(project_id: str, selected_assets: List[Dict], template_key: str, target_duration: int = 30) -> Dict[str, Any]:
    """
    Generate a structured edit plan for the reel using AI-driven decisions.
    Hybrid approach: AI makes creative decisions, structure is deterministic.
    """
    from backend.reels import REEL_TEMPLATES
    
    if not selected_assets:
        raise ValueError("No assets selected for reel")
    
    template = REEL_TEMPLATES.get(template_key, REEL_TEMPLATES["dish_showcase"])
    
    # Calculate base segment durations (deterministic foundation)
    pacing = template.get("pacing", "medium")
    base_segment_duration = {
        "slow": 4.0,
        "medium": 3.0,
        "quick": 2.0,
        "dramatic": 5.0
    }.get(pacing, 3.0)
    
    # Generate AI prompt for creative decisions
    ai_prompt = _generate_ai_edit_plan_prompt(selected_assets, template_key, template, target_duration)
    
    # Get AI-driven creative decisions (if LLM available)
    ai_decisions = None
    llm_client = get_llm_client()
    if llm_client:
        try:
            # Call LLM for creative edit planning
            ai_response = llm_client._call_llm(
                system_prompt="You are an expert Instagram Reel editor. Create engaging, punchy edit plans.",
                user_prompt=ai_prompt,
                max_tokens=800
            )
            
            # Parse AI decisions
            base_durations = [
                base_segment_duration * (1.2 if a["role"] == "intro" else 1.0 if a["role"] == "outro" else 1.0)
                for a in selected_assets
            ]
            ai_decisions = _parse_ai_edit_decisions(ai_response, selected_assets, base_durations)
            logger.info(f"AI edit plan generated for project {project_id}")
        except Exception as e:
            logger.warning(f"AI edit planning failed, using deterministic fallback: {e}")
            ai_decisions = None
    
    # Build segments (combining AI decisions with deterministic structure)
    segments = []
    current_time = 0.0
    
    for idx, asset in enumerate(selected_assets):
        media_type = asset["media_type"]
        role = asset["role"]
        
        # Get duration from AI or use deterministic calculation
        if ai_decisions and idx < len(ai_decisions):
            duration = ai_decisions[idx]["duration"]
        else:
            # Deterministic fallback
            if role == "intro":
                duration = base_segment_duration * 1.2
            elif role == "outro":
                duration = base_segment_duration * 1.0
            else:
                duration = base_segment_duration
            
            # Videos can be shorter
            if media_type == "video":
                duration = min(duration, 4.0)

        duration = _clamp_segment_duration(asset, duration, len(selected_assets), target_duration)
        
        # Ensure we don't exceed target duration
        if current_time + duration > target_duration:
            duration = target_duration - current_time
            if duration < 1.0:
                break
        
        # Determine transition (deterministic based on template)
        # First segment transition depends on template style
        if idx == 0:
            if template["transitions"] == "cut":
                transition = "hard_cut"  # Clean start for cut templates
            else:
                transition = "fade_in"  # Smooth start for other templates
        elif template["transitions"] == "smooth":
            transition = "crossfade"
        elif template["transitions"] == "cut":
            transition = "hard_cut"
        elif template["transitions"] == "fade":
            transition = "fade"
        else:
            transition = "zoom"
        
        # Build overlay text - FINAL CTA ONLY
        is_final_segment = (idx == len(selected_assets) - 1)
        overlay = _generate_segment_overlay(role, asset, template_key, idx, ai_decisions[idx] if ai_decisions else None, is_final_segment)
        
        segment = {
            "segment_id": f"seg_{idx}_{uuid.uuid4().hex[:8]}",
            "asset_id": asset["asset_id"],
            "source_path": asset["source_path"],
            "media_type": media_type,
            "role": role,
            "start_time": round(current_time, 2),
            "duration": round(duration, 2),
            "transition": transition,
            "overlay": overlay,
            "effects": _get_segment_effects(media_type, role, template_key),
            "ai_planned": ai_decisions is not None
        }
        
        segments.append(segment)
        current_time += duration
        
        if current_time >= target_duration:
            break

    _ensure_minimum_reel_duration(segments, selected_assets, target_duration)
    
    # Validate total duration
    total_duration = sum(s["duration"] for s in segments)
    
    edit_plan = {
        "plan_id": f"plan_{uuid.uuid4().hex[:12]}",
        "project_id": project_id,
        "template_key": template_key,
        "target_duration": target_duration,
        "actual_duration": round(total_duration, 2),
        "segment_count": len(segments),
        "segments": segments,
        "global_settings": {
            "output_resolution": "1080x1920",
            "frame_rate": 30,
            "video_codec": "libx264",
            "audio_codec": "aac",
            "transition_duration": 0.5
        }
    }
    
    return edit_plan


def _generate_segment_overlay(role: str, asset: Dict, template_key: str, position: int, ai_decision: Optional[Dict] = None, is_final_segment: bool = False) -> Dict[str, Any]:
    """
    Generate overlay text for a segment.
    RESTRICTED TO FINAL CTA ONLY - no text on intro/body segments.
    Only the last segment shows 'Follow for more' CTA.
    """
    # Only show text on the final segment (outro/CTA)
    if not is_final_segment:
        return {
            "text": "",
            "position": "none",
            "style": "none",
            "duration": 0
        }
    
    # Final segment CTA only
    return {
        "text": "Follow for more",
        "position": "bottom",
        "style": "cta",
        "duration": 2.0
    }


def _get_segment_effects(media_type: str, role: str, template_key: str) -> Dict[str, Any]:
    """Determine visual effects for a segment"""
    effects = {}
    
    if media_type == "image":
        # Ken Burns effect for images
        effects["ken_burns"] = {
            "enabled": True,
            "zoom_start": 1.0,
            "zoom_end": 1.15,
            "pan_direction": "random"
        }
    
    if template_key == "platter_reveal" and role == "intro":
        effects["zoom_pulse"] = {"enabled": True, "intensity": 1.2}
    
    return effects


def validate_edit_plan(edit_plan: Dict) -> tuple[bool, Optional[str]]:
    """
    Validate an edit plan before rendering.
    Returns (is_valid, error_message)
    """
    # Check required fields
    required = ["plan_id", "project_id", "segments", "target_duration", "actual_duration"]
    for field in required:
        if field not in edit_plan:
            return False, f"Missing required field: {field}"
    
    segments = edit_plan.get("segments", [])
    if not segments:
        return False, "No segments in edit plan"
    
    # Validate each segment
    for idx, seg in enumerate(segments):
        if "asset_id" not in seg:
            return False, f"Segment {idx}: missing asset_id"
        if "source_path" not in seg:
            return False, f"Segment {idx}: missing source_path"
        if "duration" not in seg or seg["duration"] <= 0:
            return False, f"Segment {idx}: invalid duration"
        
        # Check source file exists
        if not Path(seg["source_path"]).exists():
            return False, f"Segment {idx}: source file not found"
    
    # Check total duration
    total = sum(s["duration"] for s in segments)
    target = edit_plan.get("target_duration", 30)
    
    if total > target + 2:  # Allow 2 second tolerance
        return False, f"Total duration ({total}s) exceeds target ({target}s)"
    
    if total < 30:
        return False, f"Total duration ({total}s) below 30s minimum for Instagram Reels"
    
    return True, None


def update_asset_analysis_db(asset_id: str, analysis: Dict):
    """Store analysis results in database"""
    try:
        execute_insert(
            "UPDATE reel_assets SET analysis_json = ? WHERE id = ?",
            (json.dumps(analysis), asset_id)
        )
        logger.info(f"Updated analysis for asset {asset_id}")
    except DatabaseError as e:
        logger.error(f"Failed to update asset analysis {asset_id}: {e}")


def update_job_edit_plan_db(job_id: str, edit_plan: Dict):
    """Store edit plan in render job"""
    try:
        execute_insert(
            "UPDATE reel_render_jobs SET edit_plan_json = ? WHERE id = ?",
            (json.dumps(edit_plan), job_id)
        )
        logger.info(f"Updated edit plan for job {job_id}")
    except DatabaseError as e:
        logger.error(f"Failed to update job edit plan {job_id}: {e}")
