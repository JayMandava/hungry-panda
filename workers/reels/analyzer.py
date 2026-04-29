"""
Reels Maker - Phase 2: Analysis & Planning
Asset analysis, scoring, and edit plan generation
"""
import json
import uuid
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone

from infra.config.database import execute_insert, execute_query, DatabaseError
from infra.config.logging_config import logger
from infra.config.settings import config

# Import LLM client for visual analysis and edit planning
try:
    from infra.integrations.llm_client import analyze_visual_asset, LLMClient
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
    
    Phase 1 Enhancement: Extended analysis with hook_strength, food_clarity,
    motion_quality, lighting_score, orientation_fit, duplicate_group,
    usable_duration_seconds, recommended_trim_ranges, and rejection_reason.
    """
    analysis = {
        "asset_id": asset_id,
        "media_type": media_type,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "visual_facts": {},
        "quality_scores": {},
        "reel_suitability": {},
        "advanced_analysis": {}  # New: Phase 1 enhanced fields
    }
    
    try:
        # For images, run visual analysis
        if media_type == "image":
            if LLM_AVAILABLE:
                try:
                    visual_result = analyze_visual_asset(source_path)
                    visual_summary = visual_result.get("visual_summary", "").lower()
                    
                    # Infer lighting from visual summary
                    if "bright" in visual_summary or "well-lit" in visual_summary or "natural light" in visual_summary:
                        lighting_score = 0.9
                    elif "dark" in visual_summary or "dim" in visual_summary or "shadow" in visual_summary:
                        lighting_score = 0.4
                    else:
                        lighting_score = 0.7
                    
                    analysis["visual_facts"] = {
                        "dish_detected": visual_result.get("dish_detected"),
                        "meal_type": visual_result.get("meal_type"),
                        "cuisine_type": visual_result.get("cuisine_type"),
                        "visual_summary": visual_result.get("visual_summary"),
                        "primary_subject": visual_result.get("primary_subject"),
                        "confidence": visual_result.get("confidence"),
                        "is_food_content": visual_result.get("is_food_content", True),
                        "contradicts_user_text": visual_result.get("contradicts_user_text", False),
                        "lighting_score": lighting_score,
                        "motion_quality": 0.0  # Images have no motion
                    }
                except Exception as e:
                    logger.warning(f"Visual analysis failed for {asset_id}: {e}")
                    analysis["visual_facts"] = {
                        "error": str(e), 
                        "confidence": 0.5,
                        "lighting_score": 0.5,
                        "motion_quality": 0.0
                    }
            else:
                # Heuristic fallback when LLM unavailable
                analysis["visual_facts"] = _heuristic_image_analysis(source_path)
        
        elif media_type == "video":
            # For videos: extract metadata AND analyze multiple frames for richer data
            metadata = _analyze_video_metadata(source_path)
            duration = metadata.get("duration_seconds", 0)
            
            # Multi-frame sampling: analyze at 1s, 25%, 50%, 75% of duration
            frame_analyses = _analyze_video_multi_frame(source_path, asset_id, duration)
            
            # Merge metadata with aggregated visual analysis
            analysis["visual_facts"] = {
                **metadata,  # resolution, duration, frame_rate
                **frame_analyses,  # aggregated dish_detected, is_food_content, etc.
                "frame_count": frame_analyses.get("frame_count", 1),
                "analysis_source": "video_multi_frame"
            }
        
        # Score for reel suitability
        analysis["quality_scores"] = _score_asset_quality(analysis["visual_facts"], media_type)
        analysis["reel_suitability"] = _score_reel_suitability(analysis["visual_facts"], analysis["quality_scores"])
        
        # Phase 1: Enhanced advanced analysis
        analysis["advanced_analysis"] = _generate_advanced_analysis(
            analysis["visual_facts"], 
            analysis["quality_scores"],
            media_type,
            source_path
        )
        
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
            
            # Estimate lighting from image statistics (simple brightness check)
            try:
                import numpy as np
                img_gray = img.convert('L')
                brightness = np.array(img_gray).mean() / 255.0
                # Scale to lighting score (0.3-1.0 range)
                lighting_score = 0.3 + (brightness * 0.7)
            except:
                lighting_score = 0.6  # Default middle value
            
            return {
                "resolution": f"{width}x{height}",
                "aspect_ratio": round(aspect, 2),
                "confidence": 0.5,
                "is_food_content": True,  # Assume food for heuristic
                "heuristic_analysis": True,
                "lighting_score": round(lighting_score, 2),
                "motion_quality": 0.0  # Images have no motion
            }
    except Exception as e:
        return {
            "error": str(e),
            "confidence": 0.3,
            "heuristic_analysis": True,
            "lighting_score": 0.5,
            "motion_quality": 0.0
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


def _analyze_video_multi_frame(source_path: str, asset_id: str, duration: float) -> Dict[str, Any]:
    """
    Analyze multiple frames from a video for richer quality assessment.
    Samples frames at: 1s, 25%, 50%, 75% of duration (up to 4 frames max).
    Returns aggregated visual facts across all frames.
    """
    # Calculate sample timestamps
    timestamps = [1.0]  # Always sample at 1 second
    
    if duration > 4:
        timestamps.append(duration * 0.25)
    if duration > 8:
        timestamps.append(duration * 0.50)
    if duration > 12:
        timestamps.append(duration * 0.75)
    
    # Cap at 4 frames to control LLM cost
    timestamps = timestamps[:4]
    
    frame_results = []
    for ts in timestamps:
        frame_analysis = _extract_and_analyze_video_frame(source_path, asset_id, timestamp=ts)
        frame_results.append({
            "timestamp": ts,
            **frame_analysis
        })
    
    # Aggregate results across frames
    confidences = [f.get("confidence", 0.5) for f in frame_results]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
    min_confidence = min(confidences) if confidences else 0.5
    
    # Check food content consistency across frames
    food_content_votes = sum(1 for f in frame_results if f.get("is_food_content", True))
    is_food_consistent = food_content_votes >= len(frame_results) * 0.5
    
    # Aggregate dish detection (any frame detecting dish counts)
    dishes_detected = set()
    for f in frame_results:
        dish = f.get("dish_detected")
        if dish:
            dishes_detected.add(dish)
    
    # Calculate motion quality based on consistency across frames
    visual_summaries = [f.get("visual_summary", "") for f in frame_results]
    motion_quality = _calculate_motion_quality(frame_results, duration)
    
    # Lighting consistency
    lighting_scores = []
    for f in frame_results:
        summary = f.get("visual_summary", "").lower()
        if "bright" in summary or "well-lit" in summary:
            lighting_scores.append(0.9)
        elif "dark" in summary or "dim" in summary:
            lighting_scores.append(0.4)
        else:
            lighting_scores.append(0.7)
    avg_lighting = sum(lighting_scores) / len(lighting_scores) if lighting_scores else 0.7
    
    return {
        "dish_detected": list(dishes_detected)[0] if len(dishes_detected) == 1 else ("multiple" if len(dishes_detected) > 1 else None),
        "all_dishes_detected": list(dishes_detected),
        "meal_type": frame_results[0].get("meal_type") if frame_results else None,
        "cuisine_type": frame_results[0].get("cuisine_type") if frame_results else None,
        "visual_summary": visual_summaries[0] if visual_summaries else "",
        "frame_summaries": visual_summaries,
        "primary_subject": frame_results[0].get("primary_subject") if frame_results else None,
        "confidence": avg_confidence,
        "min_confidence": min_confidence,
        "is_food_content": is_food_consistent,
        "contradicts_user_text": any(f.get("contradicts_user_text", False) for f in frame_results),
        "frame_count": len(frame_results),
        "motion_quality": motion_quality,
        "lighting_score": avg_lighting,
        "frame_analysis": frame_results
    }


def _calculate_motion_quality(frame_results: List[Dict], duration: float) -> float:
    """
    Calculate motion quality score based on frame consistency and variety.
    Higher score = more engaging motion for reels.
    """
    if len(frame_results) < 2:
        return 0.6  # Default for single frame
    
    # Check for variety in visual summaries (indicates camera movement)
    summaries = [f.get("visual_summary", "").lower() for f in frame_results]
    
    # Indicators of good motion
    motion_keywords = ["moving", "pan", "zoom", "tracking", "motion", "handheld", "dynamic"]
    static_keywords = ["static", "still", "fixed", "tripod", "stable shot"]
    
    motion_score = 0.6  # Base score
    
    # Boost for detected motion keywords
    for summary in summaries:
        if any(kw in summary for kw in motion_keywords):
            motion_score += 0.15
    
    # Penalty for explicitly static shots
    for summary in summaries:
        if any(kw in summary for kw in static_keywords):
            motion_score -= 0.1
    
    # Duration factor: very short clips (<3s) or very long (>60s) are less ideal
    if 3 <= duration <= 15:
        motion_score += 0.1
    elif duration > 60:
        motion_score -= 0.1
    
    return max(0.3, min(1.0, motion_score))


def _generate_advanced_analysis(
    visual_facts: Dict, 
    quality_scores: Dict,
    media_type: str,
    source_path: str
) -> Dict[str, Any]:
    """
    Generate Phase 1 enhanced analysis fields:
    - hook_strength: 0-1 score for intro potential
    - food_clarity: 0-1 score for food visibility
    - motion_quality: 0-1 score for videos (engaging movement)
    - lighting_score: 0-1 score for illumination quality
    - orientation_fit: how well it fits 9:16 reels
    - duplicate_group: ID if this is a duplicate of another asset
    - usable_duration_seconds: for videos, how much is usable
    - recommended_trim_ranges: start/end suggestions
    - rejection_reason: if not suitable
    """
    advanced = {
        "hook_strength": 0.0,
        "food_clarity": 0.0,
        "motion_quality": 0.0,
        "lighting_score": 0.0,
        "orientation_fit": 0.0,
        "duplicate_group": None,
        "usable_duration_seconds": None,
        "recommended_trim_ranges": None,
        "rejection_reason": None,
        "version": "phase_1_enhanced"
    }
    
    # Calculate hook strength (good for intro)
    confidence = visual_facts.get("confidence", 0.5)
    is_food = visual_facts.get("is_food_content", False)
    dish = visual_facts.get("dish_detected")
    overall_quality = quality_scores.get("overall", 0.5)
    
    hook_score = overall_quality * 0.4
    if confidence > 0.8:
        hook_score += 0.25
    if is_food:
        hook_score += 0.15
    if dish:
        hook_score += 0.15
    if visual_facts.get("lighting_score", 0.7) > 0.8:
        hook_score += 0.05
    
    advanced["hook_strength"] = round(min(1.0, hook_score), 2)
    
    # Food clarity: how clearly food is visible
    if is_food:
        clarity_base = confidence * 0.5
        if dish:
            clarity_base += 0.3
        if visual_facts.get("primary_subject") == "food":
            clarity_base += 0.2
        advanced["food_clarity"] = round(min(1.0, clarity_base), 2)
    else:
        advanced["food_clarity"] = 0.1
    
    # Motion quality (videos only)
    if media_type == "video":
        advanced["motion_quality"] = round(visual_facts.get("motion_quality", 0.6), 2)
    else:
        # For images, motion quality represents dynamism potential (Ken Burns, etc.)
        # Higher for interesting compositions that could animate well
        composition = quality_scores.get("composition", 0.7)
        advanced["motion_quality"] = round(composition * 0.8, 2)
    
    # Lighting score
    advanced["lighting_score"] = round(visual_facts.get("lighting_score", 0.7), 2)
    
    # Orientation fit for 9:16 reels
    resolution = visual_facts.get("resolution", "")
    aspect_ratio = visual_facts.get("aspect_ratio", 1.0)
    
    if resolution and "x" in resolution.lower():
        try:
            w, h = map(int, resolution.lower().split('x'))
            aspect_ratio = w / h if h > 0 else 1.0
        except:
            pass
    
    # 9:16 = 0.5625 aspect ratio. Closer = better fit
    target_aspect = 9 / 16  # 0.5625
    if aspect_ratio > 0:  # Vertical/portrait
        fit = 1.0 - min(1.0, abs(aspect_ratio - target_aspect) / target_aspect)
    else:  # Landscape - needs cropping
        fit = max(0, 0.5 - abs(aspect_ratio - target_aspect))
    
    advanced["orientation_fit"] = round(fit, 2)
    
    # Usable duration and trim ranges for videos
    if media_type == "video":
        duration = visual_facts.get("duration_seconds", 0)
        
        if duration > 0:
            # Calculate usable portion (skip bad start/end if needed)
            usable_start = 0
            usable_end = duration
            
            # For very short clips, use full duration
            if duration <= 3:
                usable_start = 0
                usable_end = duration
            elif duration <= 10:
                # Good clips - maybe trim tiny bit from start if needed
                usable_start = min(0.5, duration * 0.1)
                usable_end = duration
            else:
                # Longer clips - focus on middle section for best content
                usable_start = min(1.0, duration * 0.05)
                usable_end = duration - min(1.0, duration * 0.05)
            
            usable_duration = usable_end - usable_start
            advanced["usable_duration_seconds"] = round(usable_duration, 1)
            advanced["recommended_trim_ranges"] = {
                "start_seconds": round(usable_start, 1),
                "end_seconds": round(usable_end, 1),
                "rationale": "Focus on middle content for best quality"
            }
    
    # Generate file hash for duplicate detection
    advanced["content_hash"] = _compute_file_hash(source_path)
    
    # Determine rejection reason if not suitable
    rejection_reasons = []
    
    if advanced["orientation_fit"] < 0.3:
        rejection_reasons.append("Poor orientation for 9:16 reels (landscape video)")
    
    if advanced["food_clarity"] < 0.3 and is_food:
        rejection_reasons.append("Food not clearly visible")
    
    if overall_quality < 0.4:
        rejection_reasons.append("Low visual quality")
    
    if media_type == "video" and duration < 1:
        rejection_reasons.append("Video too short (<1 second)")
    
    if media_type == "video" and advanced["motion_quality"] < 0.3:
        rejection_reasons.append("Poor motion quality (too static or shaky)")
    
    if rejection_reasons:
        advanced["rejection_reason"] = "; ".join(rejection_reasons)
    
    return advanced


def _compute_file_hash(source_path: str) -> Optional[str]:
    """Compute a quick hash of file for duplicate detection."""
    try:
        # Sample-based hash: read first 8KB + middle 8KB + last 8KB for speed
        import os
        file_size = os.path.getsize(source_path)
        
        if file_size == 0:
            return None
        
        hasher = hashlib.md5()
        
        with open(source_path, 'rb') as f:
            # First 8KB
            hasher.update(f.read(8192))
            
            # Middle 8KB if file is large enough
            if file_size > 24576:  # > 24KB
                f.seek(file_size // 2)
                hasher.update(f.read(8192))
            
            # Last 8KB
            if file_size > 8192:
                f.seek(-8192, 2)
                hasher.update(f.read(8192))
        
        return hasher.hexdigest()[:16]  # 16 chars is enough for deduplication
    except Exception as e:
        logger.warning(f"Failed to compute file hash for {source_path}: {e}")
        return None


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
            # Allow extending beyond source duration — renderer pads short videos with tpad (freeze last frame)
            max_for_video = 15.0
            extendable_room.append((i, current_dur, max_for_video))
            total_extendable += max_for_video
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

def generate_edit_plan(project_id: str, selected_assets: List[Dict], template_key: str, target_duration: int = 30, transition_style: str = "auto") -> Dict[str, Any]:
    """
    Generate a structured edit plan for the reel using AI-driven decisions.
    Hybrid approach: AI makes creative decisions, structure is deterministic.
    
    Args:
        project_id: The reel project ID
        selected_assets: List of selected assets for the reel
        template_key: Template to use for styling
        target_duration: Target duration in seconds
        transition_style: Transition style - auto, cut, smooth, fade (user override wins)
    """
    from shared.reel_templates import REEL_TEMPLATES
    
    if not selected_assets:
        raise ValueError("No assets selected for reel")
    
    template = REEL_TEMPLATES.get(template_key, REEL_TEMPLATES["dish_showcase"])
    
    # Use user-selected transition style, or fall back to template default
    # Valid transitions: hard_cut, crossfade, fade, smooth
    if transition_style == "auto":
        # Use template default
        transition_map = {
            "cut": "hard_cut",
            "smooth": "crossfade",
            "fade": "fade",
        }
        template_transition = template.get("transitions", "smooth")
        effective_transition = transition_map.get(template_transition, "crossfade")
    elif transition_style == "cut":
        effective_transition = "hard_cut"
    elif transition_style in ["smooth", "fade"]:
        effective_transition = "crossfade"  # Both map to crossfade for now
    else:
        effective_transition = "crossfade"  # Default fallback
    
    logger.info(f"Edit plan for project {project_id}: transition_style={transition_style}, effective={effective_transition}")
    
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
        
        # Determine transition based on user-selected transition_style (overrides template)
        # First segment transition (no transition from previous)
        if idx == 0:
            if effective_transition == "hard_cut":
                transition = "hard_cut"  # Clean start for cut style
            else:
                transition = "fade_in"  # Smooth start for other styles
        else:
            # Use the effective transition style selected by user
            transition = effective_transition
        
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
            "transition_duration": 0.5,
            "transition_style": transition_style,
            "effective_transition": effective_transition
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
    
    # Short plans (< 30s) are padded to 30s by the renderer via tpad — not a hard failure
    if total < 3:
        return False, f"Total duration ({total}s) too short — need at least a few seconds of content"

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
