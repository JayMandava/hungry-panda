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
        
        # Phase 1: Generate quality scores first
        analysis["quality_scores"] = _score_asset_quality(analysis["visual_facts"], media_type)
        
        # Phase 1: Generate enhanced advanced analysis (needed for smart selection)
        analysis["advanced_analysis"] = _generate_advanced_analysis(
            analysis["visual_facts"], 
            analysis["quality_scores"],
            media_type,
            source_path
        )
        
        # Phase 1: Score reel suitability using advanced metrics
        analysis["reel_suitability"] = _score_reel_suitability(
            analysis["visual_facts"], 
            analysis["quality_scores"],
            analysis["advanced_analysis"]  # Now passed for enhanced scoring
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
    Samples frames at: 0.5s (or 25% if <1s), 25%, 50%, 75% of duration (up to 4 frames max).
    Returns aggregated visual facts across all frames.
    """
    # Calculate sample timestamps based on video duration
    timestamps = []
    
    if duration < 1.0:
        # Sub-second videos: sample at 25% of duration (avoid going past end)
        timestamps.append(duration * 0.25)
    elif duration < 2.0:
        # Very short clips: sample at 0.5s
        timestamps.append(0.5)
    else:
        # Normal videos: start at 1s
        timestamps.append(1.0)
    
    # Add percentage-based samples for longer videos
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


def _score_reel_suitability(
    visual_facts: Dict, 
    quality_scores: Dict,
    advanced_analysis: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Score asset for specific reel roles (intro, body, outro).
    Phase 1: Now uses advanced_analysis fields for smarter scoring.
    """
    overall = quality_scores.get("overall", 0.7)
    advanced = advanced_analysis or {}
    
    # Get enhanced metrics (fallback to neutral if not available)
    hook_strength = advanced.get("hook_strength", overall)
    orientation_fit = advanced.get("orientation_fit", 0.7)
    motion_quality = advanced.get("motion_quality", 0.6)
    rejection_reason = advanced.get("rejection_reason")
    
    # Check for hard disqualifiers from rejection_reason
    disqualified = False
    if rejection_reason:
        # Parse rejection reasons - some are hard blocks, some are warnings
        hard_blocks = [
            "Video too short",
            "Poor orientation for 9:16 reels",
            "file not found",
            "corrupted"
        ]
        for block in hard_blocks:
            if block.lower() in rejection_reason.lower():
                disqualified = True
                break
    
    # Severe orientation misfit is a hard disqualifier
    if orientation_fit < 0.2:
        disqualified = True
    
    # Determine best role using enhanced metrics
    role_scores = {
        "intro": hook_strength * 0.95,  # Use hook_strength directly for intro
        "body": overall * 0.9,            # Slightly penalized - body needs balance
        "outro": overall * 0.85           # More penalized - outro needs CTA + closure
    }
    
    # Apply multipliers based on quality signals
    confidence = visual_facts.get("confidence", 0.7)
    is_food = visual_facts.get("is_food_content", True)
    dish = visual_facts.get("dish_detected")
    
    # Boost intro for hero shots with all quality signals
    if hook_strength > 0.7 and is_food and dish and orientation_fit > 0.7:
        role_scores["intro"] *= 1.15
    
    # Motion quality affects all roles (better motion = more engaging)
    if motion_quality > 0.7:
        role_scores["intro"] *= 1.05
        role_scores["body"] *= 1.1
    elif motion_quality < 0.4:
        # Poor motion hurts body more (intro can be static hero, outro can be CTA)
        role_scores["body"] *= 0.85
    
    # Orientation fit penalty for all roles
    if orientation_fit < 0.5:
        penalty = 0.7 + (orientation_fit * 0.3)  # 0.5 fit = 0.85 penalty, 0.2 fit = 0.76 penalty
        for role in role_scores:
            role_scores[role] *= penalty
    
    # Determine best role
    best_role = max(role_scores, key=role_scores.get)
    final_score = role_scores[best_role]
    
    # Disqualified assets get low score and not recommended
    if disqualified:
        final_score = min(final_score, 0.3)
        is_recommended = False
    else:
        # Normal recommendation threshold
        is_recommended = final_score >= 0.55 and orientation_fit >= 0.3
    
    return {
        "role": best_role,
        "role_scores": role_scores,
        "score": round(final_score, 2),
        "recommended": is_recommended,
        "disqualified": disqualified,
        "orientation_penalty": orientation_fit < 0.5,
        "motion_bonus": motion_quality > 0.7
    }


def _detect_duplicate_assets(assets: List[Dict]) -> Dict[str, str]:
    """
    Detect duplicate assets by content_hash.
    Returns dict mapping duplicate asset_id -> original asset_id.
    First occurrence is kept as original.
    """
    seen_hashes: Dict[str, str] = {}  # hash -> first asset_id
    duplicates: Dict[str, str] = {}  # duplicate_id -> original_id
    
    for asset in assets:
        analysis = asset.get("analysis_json", {})
        advanced = analysis.get("advanced_analysis", {})
        content_hash = advanced.get("content_hash")
        asset_id = asset["id"]
        
        if content_hash:
            if content_hash in seen_hashes:
                # This is a duplicate
                duplicates[asset_id] = seen_hashes[content_hash]
                logger.info(f"Detected duplicate: {asset_id} is duplicate of {seen_hashes[content_hash]}")
            else:
                # First occurrence
                seen_hashes[content_hash] = asset_id
    
    return duplicates


def _call_ai_director_selection(
    qualified_assets: List[Dict],
    target_duration: int
) -> Optional[Dict[str, Any]]:
    """
    Phase 2: AI-assisted clip selection.
    
    Uses LLM to select and rank clips for intro, body, and outro roles.
    Returns director decisions with rationale, or None if LLM unavailable/invalid.
    
    The LLM works within validated bounds - it can only select from qualified assets
    and its decisions are validated against deterministic scoring.
    """
    if not LLM_AVAILABLE or len(qualified_assets) < 2:
        return None
    
    llm_client = get_llm_client()
    if not llm_client:
        return None
    
    # Build comprehensive asset descriptions for the LLM
    asset_descriptions = []
    for idx, asset in enumerate(qualified_assets):
        analysis = asset.get("analysis_json", {})
        advanced = analysis.get("advanced_analysis", {})
        visual = analysis.get("visual_facts", {})
        
        desc = f"\nAsset {idx+1} (ID: {asset['id'][:8]}):\n"
        desc += f"  Type: {asset['media_type']}\n"
        desc += f"  Dish: {visual.get('dish_detected', 'Unknown')}\n"
        desc += f"  Visual: {visual.get('visual_summary', 'N/A')[:80]}\n"
        desc += f"  Quality Metrics:\n"
        desc += f"    - Hook strength: {advanced.get('hook_strength', 0):.2f}/1.0\n"
        desc += f"    - Food clarity: {advanced.get('food_clarity', 0):.2f}/1.0\n"
        desc += f"    - Motion quality: {advanced.get('motion_quality', 0):.2f}/1.0\n"
        desc += f"    - Orientation fit: {advanced.get('orientation_fit', 0):.2f}/1.0\n"
        desc += f"    - Overall score: {analysis.get('reel_suitability', {}).get('score', 0):.2f}/1.0\n"
        
        if asset['media_type'] == 'video':
            desc += f"    - Duration: {visual.get('duration_seconds', 0):.1f}s\n"
            desc += f"    - Usable duration: {advanced.get('usable_duration_seconds', 0):.1f}s\n"
        
        asset_descriptions.append(desc)
    
    prompt = f"""You are an expert Instagram Reel editor selecting clips for a {target_duration}s reel.

You must choose the best clips for three roles:
- INTRO (1 clip): Needs strong hook to grab attention in first 3 seconds. Prioritize hook_strength > 0.7.
- BODY (1-3 clips): Needs engaging motion and good food clarity. Prioritize motion_quality and food_clarity.
- OUTRO (1 clip): Needs clear food visibility for CTA/call-to-action. Prioritize food_clarity > 0.7.

AVAILABLE ASSETS:
{''.join(asset_descriptions)}

SELECTION RULES:
1. You MUST select 3-5 assets total (1 intro + 1-3 body + 1 outro)
2. Do NOT select the same asset for multiple roles
3. Consider asset durations - short clips (<3s) work better for intro, longer for body
4. If an asset has rejection_reason populated, avoid selecting it
5. Videos with high motion_quality (>0.7) are preferred for body

Respond in this exact JSON format:
{{
  "selections": [
    {{"asset_index": 1, "role": "intro", "rationale": "Strong hook with close-up of dish"}},
    {{"asset_index": 3, "role": "body", "rationale": "Good motion showing cooking process"}},
    {{"asset_index": 5, "role": "outro", "rationale": "Clear plated dish for CTA"}}
  ],
  "skipped_indices": [2, 4],
  "overall_strategy": "Brief explanation of your selection approach"
}}

Asset indices are 1-based (Asset 1 = index 1)."""

    try:
        # Call LLM for director decisions
        system_prompt = "You are an expert video editor. Respond only with valid JSON in the exact format requested."
        ai_response = llm_client._call_llm(
            system_prompt=system_prompt,
            user_prompt=prompt,
            max_tokens=600
        )
        
        # Parse JSON response
        try:
            director_decisions = json.loads(ai_response.strip())
        except json.JSONDecodeError:
            # Try to extract JSON from response if wrapped in markdown
            import re
            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
            if json_match:
                director_decisions = json.loads(json_match.group(0))
            else:
                logger.warning(f"AI director returned invalid JSON: {ai_response[:200]}")
                return None
        
        # Validate the decisions
        valid_selections = []
        seen_asset_ids = set()
        
        for sel in director_decisions.get("selections", []):
            idx = sel.get("asset_index", 0) - 1  # Convert to 0-based
            if 0 <= idx < len(qualified_assets):
                asset = qualified_assets[idx]
                asset_id = asset["id"]
                
                # Don't select same asset twice
                if asset_id in seen_asset_ids:
                    logger.warning(f"AI director tried to select same asset twice: {asset_id}")
                    continue
                
                # Validate role is one we accept
                role = sel.get("role", "body")
                if role not in ["intro", "body", "outro"]:
                    role = "body"
                
                seen_asset_ids.add(asset_id)
                valid_selections.append({
                    "asset_id": asset_id,
                    "asset": asset,
                    "role": role,
                    "rationale": sel.get("rationale", "Selected by AI director"),
                    "source": "ai_director"
                })
        
        # Phase 2: Validate role contract - must have 1 intro + 1-3 body + 1 outro
        role_counts = {"intro": 0, "body": 0, "outro": 0}
        for sel in valid_selections:
            role = sel.get("role", "body")
            if role in role_counts:
                role_counts[role] += 1
        
        # Contract: exactly 1 intro, 1-3 body, exactly 1 outro
        has_valid_structure = (
            role_counts["intro"] == 1 and
            1 <= role_counts["body"] <= 3 and
            role_counts["outro"] == 1 and
            3 <= len(valid_selections) <= 5
        )
        
        if not has_valid_structure:
            logger.warning(
                f"AI director violated role contract: intro={role_counts['intro']}, "
                f"body={role_counts['body']}, outro={role_counts['outro']}. "
                f"Required: 1 intro + 1-3 body + 1 outro. Falling back to deterministic."
            )
            return None
        
        # Build skipped list
        selected_indices = {s["asset_id"] for s in valid_selections}
        skipped = [a["id"] for a in qualified_assets if a["id"] not in selected_indices]
        
        logger.info(f"AI director selected {len(valid_selections)} assets: {role_counts} with rationale")
        
        return {
            "selections": valid_selections,
            "skipped_asset_ids": skipped,
            "overall_strategy": director_decisions.get("overall_strategy", "AI-assisted selection"),
            "source": "ai_director",
            "fallback": False
        }
        
    except Exception as e:
        logger.warning(f"AI director selection failed: {e}")
        return None


def select_assets_for_reel(assets: List[Dict], target_duration: int = 30) -> List[Dict]:
    """
    Phase 2: AI-assisted director selection with deterministic fallback.
    
    Key improvements:
    - First attempts AI director selection (LLM chooses best clips)
    - Falls back to deterministic scoring if AI unavailable/invalid
    - Uses hook_strength, motion_quality, orientation_fit for ranking
    - Filters out disqualified assets (poor orientation, rejection_reason)
    - Detects and suppresses duplicate uploads
    - Assigns intro/body/outro based on quality scores
    - Stores selection rationale and skipped assets in result
    """
    if not assets:
        return []
    
    # Phase 1: Detect duplicates first
    duplicates = _detect_duplicate_assets(assets)
    
    # Filter out duplicates from consideration (keep originals)
    unique_assets = [a for a in assets if a["id"] not in duplicates]
    
    # Sort by upload order initially
    sorted_assets = sorted(unique_assets, key=lambda x: x.get("sort_order", 0))
    
    # Filter to qualified assets only
    qualified = []
    disqualified = []
    
    for asset in sorted_assets:
        analysis = asset.get("analysis_json", {})
        suitability = analysis.get("reel_suitability", {})
        advanced = analysis.get("advanced_analysis", {})
        
        # Hard disqualifiers
        is_disqualified = suitability.get("disqualified", False)
        orientation_fit = advanced.get("orientation_fit", 0.7)
        rejection_reason = advanced.get("rejection_reason")
        
        if is_disqualified or orientation_fit < 0.2:
            disqualified.append({
                "asset_id": asset["id"],
                "reason": rejection_reason or f"orientation_fit={orientation_fit:.2f}"
            })
            continue
        
        qualified.append(asset)
    
    if not qualified:
        # Emergency fallback: use assets with highest scores, even if not recommended
        logger.warning("No qualified assets found, falling back to best available")
        # Score all unique assets by overall quality
        scored = []
        for idx, asset in enumerate(sorted_assets):
            analysis = asset.get("analysis_json", {})
            suitability = analysis.get("reel_suitability", {})
            score = suitability.get("score", 0.5)
            # Include index as tie-breaker to avoid dict comparison errors
            scored.append((score, idx, asset))
        
        scored.sort(reverse=True, key=lambda x: (x[0], -x[1]))  # Higher score wins, lower index breaks ties
        qualified = [asset for _, _, asset in scored[:4]]  # Take top 4 at most
    
    # Log disqualified assets
    if disqualified:
        logger.info(f"Disqualified {len(disqualified)} assets: {disqualified}")
    
    # Phase 2: Try AI director selection first
    ai_director_result = None
    if len(qualified) >= 2:
        try:
            ai_director_result = _call_ai_director_selection(qualified, target_duration)
            if ai_director_result:
                logger.info(f"Using AI director selection: {ai_director_result.get('overall_strategy', 'AI-assisted')}")
        except Exception as e:
            logger.warning(f"AI director failed, will use deterministic fallback: {e}")
    
    # If AI director gave us valid selections, use them
    if ai_director_result and ai_director_result.get("selections"):
        return _build_selection_from_director(
            ai_director_result, 
            qualified, 
            duplicates,
            disqualified
        )
    
    # Otherwise, fall back to deterministic scoring (Phase 1)
    logger.info("Using deterministic asset selection (AI director unavailable)")
    
    # Phase 1: Score-based role assignment
    # First, identify the best intro candidate by hook_strength
    intro_candidates = []
    for asset in qualified:
        analysis = asset.get("analysis_json", {})
        advanced = analysis.get("advanced_analysis", {})
        suitability = analysis.get("reel_suitability", {})
        
        hook_strength = advanced.get("hook_strength", 0.5)
        score = suitability.get("score", 0.5)
        orientation_fit = advanced.get("orientation_fit", 0.7)
        
        # Combined intro score: hook + quality + orientation
        intro_score = (hook_strength * 0.5) + (score * 0.3) + (orientation_fit * 0.2)
        intro_candidates.append((intro_score, asset))
    
    # Sort by intro potential
    intro_candidates.sort(reverse=True, key=lambda x: x[0])
    
    # Assign intro to the best candidate (not just first uploaded)
    intro_asset = intro_candidates[0][1] if intro_candidates else None
    intro_id = intro_asset["id"] if intro_asset else None
    
    # Remaining assets for body/outro
    remaining = [a for a in qualified if a["id"] != intro_id]
    
    # Score remaining for body vs outro
    body_outro_candidates = []
    for asset in remaining:
        analysis = asset.get("analysis_json", {})
        advanced = analysis.get("advanced_analysis", {})
        suitability = analysis.get("reel_suitability", {})
        
        score = suitability.get("score", 0.5)
        motion_quality = advanced.get("motion_quality", 0.6)
        food_clarity = advanced.get("food_clarity", 0.5)
        
        # Body assets need good motion + clarity
        body_score = (score * 0.4) + (motion_quality * 0.35) + (food_clarity * 0.25)
        
        # Outro needs HIGH clarity for CTA visibility, score still matters, motion less important
        outro_score = (food_clarity * 0.45) + (score * 0.4) + (motion_quality * 0.15)
        
        body_outro_candidates.append({
            'asset': asset,
            'body_score': body_score,
            'outro_score': outro_score,
            'food_clarity': food_clarity
        })
    
    # Calculate how many of each role we need
    total_needed = min(len(qualified), 6)  # Max 6 assets total
    num_outro = min(2, max(0, len(body_outro_candidates) - 2))  # 0-2 outro
    num_body = total_needed - 1 - num_outro  # Rest are body (minus intro)
    
    # Strategy: Pick best outro FIRST by outro_score, then fill body with what's left
    # This ensures outro gets assets optimized for CTA/clarity, not leftovers
    
    # Sort by outro_score (descending) to find best outro candidates
    outro_sorted = sorted(body_outro_candidates, reverse=True, key=lambda x: x['outro_score'])
    outro_selection = outro_sorted[:num_outro]
    outro_ids = {c['asset']['id'] for c in outro_selection}
    
    # Remaining candidates for body (exclude outro picks)
    remaining_for_body = [c for c in body_outro_candidates if c['asset']['id'] not in outro_ids]
    
    # Sort remaining by body_score (motion + clarity + quality)
    body_sorted = sorted(remaining_for_body, reverse=True, key=lambda x: x['body_score'])
    body_selection = body_sorted[:num_body]
    
    body_assets = [c['asset'] for c in body_selection]
    outro_assets = [c['asset'] for c in outro_selection]
    
    # Build final selection with assigned roles
    selected = []
    
    # Intro first
    if intro_asset:
        analysis = intro_asset.get("analysis_json", {})
        suitability = analysis.get("reel_suitability", {})
        selected.append({
            "asset_id": intro_asset["id"],
            "source_path": intro_asset["source_path"],
            "media_type": intro_asset["media_type"],
            "sort_order": intro_asset.get("sort_order", 0),
            "role": "intro",
            "score": suitability.get("score", 0.5),
            "hook_strength": analysis.get("advanced_analysis", {}).get("hook_strength", 0),
            "selection_reason": "Highest hook_strength for intro",
            "analysis": analysis
        })
    
    # Body assets
    for asset in body_assets:
        analysis = asset.get("analysis_json", {})
        suitability = analysis.get("reel_suitability", {})
        advanced = analysis.get("advanced_analysis", {})
        selected.append({
            "asset_id": asset["id"],
            "source_path": asset["source_path"],
            "media_type": asset["media_type"],
            "sort_order": asset.get("sort_order", 0),
            "role": "body",
            "score": suitability.get("score", 0.5),
            "motion_quality": advanced.get("motion_quality", 0),
            "selection_reason": "Strong motion + food clarity for body",
            "analysis": analysis
        })
    
    # Outro assets
    for asset in outro_assets:
        analysis = asset.get("analysis_json", {})
        suitability = analysis.get("reel_suitability", {})
        advanced = analysis.get("advanced_analysis", {})
        selected.append({
            "asset_id": asset["id"],
            "source_path": asset["source_path"],
            "media_type": asset["media_type"],
            "sort_order": asset.get("sort_order", 0),
            "role": "outro",
            "score": suitability.get("score", 0.5),
            "food_clarity": advanced.get("food_clarity", 0),
            "selection_reason": "Clear food visibility for outro CTA",
            "analysis": analysis
        })
    
    # Mark duplicates with references
    for dup_id, orig_id in duplicates.items():
        if orig_id in [s["asset_id"] for s in selected]:
            # Find the selected asset that this is a duplicate of
            for sel in selected:
                if sel["asset_id"] == orig_id:
                    sel["has_duplicates"] = sel.get("has_duplicates", []) + [dup_id]
    
    logger.info(f"Selected {len(selected)} assets: {[(s['asset_id'][:8], s['role']) for s in selected]}")
    
    return selected


def _build_selection_from_director(
    director_result: Dict[str, Any],
    qualified_assets: List[Dict],
    duplicates: Dict[str, str],
    disqualified_list: List[Dict]
) -> List[Dict]:
    """
    Build final selection list from AI director decisions.
    Includes rationale, marks skipped assets, and adds metadata.
    """
    selected = []
    
    # Build lookup from asset_id to full asset data
    asset_lookup = {a["id"]: a for a in qualified_assets}
    
    # Process AI selections
    for sel in director_result["selections"]:
        asset_id = sel["asset_id"]
        asset = asset_lookup.get(asset_id)
        if not asset:
            continue
        
        analysis = asset.get("analysis_json", {})
        suitability = analysis.get("reel_suitability", {})
        advanced = analysis.get("advanced_analysis", {})
        
        selected.append({
            "asset_id": asset_id,
            "source_path": asset["source_path"],
            "media_type": asset["media_type"],
            "sort_order": asset.get("sort_order", 0),
            "role": sel["role"],
            "score": suitability.get("score", 0.5),
            "hook_strength": advanced.get("hook_strength", 0),
            "motion_quality": advanced.get("motion_quality", 0),
            "food_clarity": advanced.get("food_clarity", 0),
            "selection_reason": sel.get("rationale", "Selected by AI director"),
            "selection_source": "ai_director",
            "selection_strategy": director_result.get("overall_strategy", ""),
            "analysis": analysis
        })
    
    # Mark duplicates
    for dup_id, orig_id in duplicates.items():
        if orig_id in [s["asset_id"] for s in selected]:
            for sel in selected:
                if sel["asset_id"] == orig_id:
                    sel["has_duplicates"] = sel.get("has_duplicates", []) + [dup_id]
    
    # Log skipped assets for debugging
    skipped_ids = director_result.get("skipped_asset_ids", [])
    if skipped_ids:
        logger.info(f"AI director skipped {len(skipped_ids)} assets: {skipped_ids[:5]}")
    
    # Log disqualified
    if disqualified_list:
        logger.info(f"AI director excluded {len(disqualified_list)} disqualified assets")
    
    logger.info(f"AI director final selection: {[(s['asset_id'][:8], s['role']) for s in selected]}")
    
    return selected


def update_asset_selected_status(project_id: str, selected_assets: List[Dict], all_assets: List[Dict]):
    """
    Phase 2: Update the 'selected' field in database for all project assets.
    - Selected assets: selected = 1
    - Skipped/Disqualified assets: selected = 0
    - Stores skip rationale in analysis_json
    """
    selected_ids = {s["asset_id"] for s in selected_assets}
    
    updates = []
    for asset in all_assets:
        asset_id = asset["id"]
        is_selected = asset_id in selected_ids
        
        # Find skip reason if not selected
        skip_reason = None
        if not is_selected:
            # Check if disqualified
            analysis = asset.get("analysis_json", {})
            suitability = analysis.get("reel_suitability", {})
            advanced = analysis.get("advanced_analysis", {})
            
            if suitability.get("disqualified"):
                skip_reason = advanced.get("rejection_reason") or "Disqualified by quality checks"
            elif advanced.get("duplicate_of"):
                original_id = advanced['duplicate_of']
                skip_reason = f"Duplicate of {original_id[:8]}"
            else:
                skip_reason = "Not selected by director (better alternatives available)"
            
            # Update analysis_json with skip info
            if advanced:
                advanced["selected"] = False
                advanced["skip_reason"] = skip_reason
                advanced["selected_at"] = datetime.now(timezone.utc).isoformat()
                
                try:
                    execute_insert(
                        "UPDATE reel_assets SET analysis_json = ?, selected = 0 WHERE id = ?",
                        (json.dumps(analysis), asset_id)
                    )
                    updates.append((asset_id, False, skip_reason))
                except DatabaseError as e:
                    logger.error(f"Failed to update skipped asset {asset_id}: {e}")
        else:
            # Mark as selected
            analysis = asset.get("analysis_json", {})
            advanced = analysis.get("advanced_analysis", {})
            if advanced:
                advanced["selected"] = True
                advanced["selected_at"] = datetime.now(timezone.utc).isoformat()
            
            try:
                execute_insert(
                    "UPDATE reel_assets SET analysis_json = ?, selected = 1 WHERE id = ?",
                    (json.dumps(analysis), asset_id)
                )
                updates.append((asset_id, True, "Selected for reel"))
            except DatabaseError as e:
                logger.error(f"Failed to update selected asset {asset_id}: {e}")
    
    logger.info(f"Updated selected status for {len(updates)} assets: {sum(1 for _, s, _ in updates if s)} selected, {sum(1 for _, s, _ in updates if not s)} skipped")


# Phase 1 Work Item 3: Strict JSON schema for AI edit planning
EDIT_PLAN_JSON_SCHEMA = {
    "type": "object",
    "required": ["segments", "total_duration_seconds", "rationale"],
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["asset_index", "duration_seconds", "transition", "effect_notes"],
                "properties": {
                    "asset_index": {"type": "integer", "minimum": 0, "description": "0-based index of the asset"},
                    "duration_seconds": {"type": "number", "minimum": 1.0, "maximum": 10.0, "description": "Duration for this segment"},
                    "transition": {"type": "string", "enum": ["hard_cut", "crossfade", "fade", "fade_in"], "description": "Transition type"},
                    "effect_notes": {"type": "string", "maxLength": 200, "description": "Brief effect description (e.g., 'Ken Burns zoom', 'quick cut')"},
                    "overlay_text": {"type": "string", "maxLength": 50, "description": "Optional overlay text (keep empty for most segments)"}
                }
            }
        },
        "total_duration_seconds": {"type": "number", "minimum": 25, "maximum": 65, "description": "Total planned duration"},
        "rationale": {"type": "string", "maxLength": 500, "description": "Brief explanation of edit decisions"}
    }
}


def _generate_ai_edit_plan_json_prompt(selected_assets: List[Dict], template_key: str, template: Dict, target_duration: int) -> str:
    """
    Phase 1 Work Item 3: Generate strict JSON prompt for AI edit planning.
    Returns a prompt that enforces structured JSON output via LLM json_mode.
    """
    # Build asset descriptions with indices
    asset_descriptions = []
    for idx, asset in enumerate(selected_assets):
        analysis = asset.get("analysis", {})
        visual = analysis.get("visual_facts", {})
        advanced = analysis.get("advanced_analysis", {})

        desc_parts = [f"[{idx}] {asset['media_type'].upper()}", f"role={asset['role']}"]
        if visual.get("dish_detected"):
            desc_parts.append(f"dish={visual['dish_detected']}")
        if advanced.get("hook_strength"):
            desc_parts.append(f"hook={advanced['hook_strength']:.2f}")
        if advanced.get("food_clarity"):
            desc_parts.append(f"clarity={advanced['food_clarity']:.2f}")
        if visual.get("visual_summary"):
            desc_parts.append(f"summary={visual['visual_summary'][:80]}")

        asset_descriptions.append(" | ".join(desc_parts))

    # Valid transitions for renderer contract
    valid_transitions = ["hard_cut", "crossfade", "fade", "fade_in"]

    prompt = f"""You are a professional video editor creating an Instagram Reel edit plan.

TEMPLATE: {template_key}
Style: {template.get('name', 'Custom')}
Description: {template.get('description', '')}
Pacing: {template.get('pacing', 'medium')}
Target duration: {target_duration} seconds (stay within 2s of this target)

ASSETS ({len(selected_assets)} total):
{chr(10).join(asset_descriptions)}

Create an engaging edit plan following these rules:
- First segment (intro) needs strong hook - use fade_in or crossfade
- Body segments maintain energy with hard_cut or crossfade
- Last segment (outro) should have satisfying conclusion - use crossfade or fade
- Keep individual segments between 2-6 seconds
- Total duration must be close to {target_duration}s (within 25-65s range)
- Only use supported transitions: {', '.join(valid_transitions)}
- Effect notes should be brief (Ken Burns zoom, quick cut, hold for reveal)
- Overlay text should be minimal (only for key moments, max 50 chars)

STRICT JSON OUTPUT FORMAT:
```json
{{
  "segments": [
    {{
      "asset_index": 0,
      "duration_seconds": 3.5,
      "transition": "fade_in",
      "effect_notes": "Strong hook with Ken Burns",
      "overlay_text": ""
    }}
  ],
  "total_duration_seconds": {target_duration},
  "rationale": "Brief explanation of pacing and transition choices"
}}
```

Respond with ONLY valid JSON matching the schema above."""

    return prompt


def _parse_ai_edit_plan_json(ai_response: str, selected_assets: List[Dict], target_duration: int) -> Optional[List[Dict]]:
    """
    Phase 1 Work Item 3: Parse and validate strict JSON edit plan from AI response.
    Returns list of decisions or None if invalid (triggers deterministic fallback).
    """
    import json

    try:
        # Parse JSON response
        parsed = json.loads(ai_response.strip())

        # Validate required fields
        if "segments" not in parsed:
            logger.warning("AI edit plan missing 'segments' field")
            return None
        if "total_duration_seconds" not in parsed:
            logger.warning("AI edit plan missing 'total_duration_seconds' field")
            return None

        segments = parsed["segments"]
        if not isinstance(segments, list) or len(segments) == 0:
            logger.warning("AI edit plan has empty or invalid segments")
            return None

        # Validate total duration is within tolerance
        total = parsed["total_duration_seconds"]
        if not (25 <= total <= 65):
            logger.warning(f"AI edit plan total duration {total}s out of valid range (25-65s)")
            return None

        # Build decisions from validated segments
        decisions = []
        valid_transitions = {"hard_cut", "crossfade", "fade", "fade_in"}

        for seg in segments:
            # Validate asset_index
            asset_idx = seg.get("asset_index")
            if not isinstance(asset_idx, int) or asset_idx < 0 or asset_idx >= len(selected_assets):
                logger.warning(f"AI edit plan invalid asset_index: {asset_idx}")
                continue

            # Validate duration
            duration = seg.get("duration_seconds", 3.0)
            if not isinstance(duration, (int, float)) or not (1.0 <= duration <= 10.0):
                logger.warning(f"AI edit plan invalid duration for asset {asset_idx}: {duration}")
                duration = 3.0  # Clamp to safe default

            # Validate transition
            transition = seg.get("transition", "crossfade")
            if transition not in valid_transitions:
                logger.warning(f"AI edit plan unsupported transition '{transition}', defaulting to crossfade")
                transition = "crossfade"

            decisions.append({
                "asset_index": asset_idx,
                "duration": float(duration),
                "transition": transition,
                "effect_notes": seg.get("effect_notes", "")[:200],
                "overlay_text": seg.get("overlay_text", "")[:50],
                "ai_planned": True
            })

        # Ensure we have at least one valid decision
        if not decisions:
            logger.warning("AI edit plan produced no valid segment decisions")
            return None

        logger.info(f"Parsed AI edit plan JSON: {len(decisions)} segments, {total}s total duration")
        return decisions

    except json.JSONDecodeError as e:
        logger.warning(f"AI edit plan JSON parse failed: {e}")
        return None
    except Exception as e:
        logger.warning(f"AI edit plan validation failed: {e}")
        return None


# Legacy prose-based prompt (deprecated, kept for reference)
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

# Legacy regex-based parser (deprecated, replaced by _parse_ai_edit_plan_json)
def _parse_ai_edit_decisions(ai_response: str, selected_assets: List[Dict], base_durations: List[float]) -> List[Dict]:
    """Parse AI response into edit decisions, with fallback to base durations. DEPRECATED: Use _parse_ai_edit_plan_json."""
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
            rf'(?i)(asset\s*{idx+1}[^\n]{0,100}|segment\s*{idx+1}[^\n]{0,100})(.*?)(?=asset\s*{idx+2}|segment\s*{idx+2}|$)',
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

def generate_edit_plan(
    project_id: str,
    selected_assets: List[Dict],
    template_key: str,
    target_duration: int = 30,
    transition_style: str = "auto",
    visual_filter: str = "none",
    all_assets: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """
    Generate a structured edit plan for the reel using AI-driven decisions.
    Hybrid approach: AI makes creative decisions, structure is deterministic.

    Phase 3: Enhanced edit plan with schema versioning and complete metadata.

    Args:
        project_id: The reel project ID
        selected_assets: List of selected assets for the reel
        template_key: Template to use for styling
        target_duration: Target duration in seconds
        transition_style: Transition style - auto, cut, smooth, fade (user override wins)
        visual_filter: Visual filter preset - none, natural, warm, rich, fresh
        all_assets: Optional list of all project assets for selection rationale
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
    
    # Phase 1 Work Item 3: Generate strict JSON AI prompt for creative decisions
    ai_prompt_json = _generate_ai_edit_plan_json_prompt(selected_assets, template_key, template, target_duration)

    # Get AI-driven creative decisions (if LLM available) using strict JSON mode
    ai_segment_decisions = None
    llm_client = get_llm_client()
    if llm_client:
        try:
            # Call LLM with json_mode=True for structured output
            ai_response = llm_client._call_llm(
                system_prompt="You are an expert Instagram Reel editor. Create engaging edit plans. Respond ONLY with valid JSON matching the provided schema.",
                user_prompt=ai_prompt_json,
                max_tokens=800,
                json_mode=True  # Phase 1 Work Item 3: Enforce strict JSON output
            )

            # Parse AI decisions using strict JSON parser
            ai_segment_decisions = _parse_ai_edit_plan_json(ai_response, selected_assets, target_duration)
            if ai_segment_decisions:
                logger.info(f"AI edit plan JSON parsed successfully for project {project_id}: {len(ai_segment_decisions)} segments")
            else:
                logger.warning(f"AI edit plan JSON invalid or empty, will use deterministic fallback for project {project_id}")
        except Exception as e:
            logger.warning(f"AI edit planning failed, using deterministic fallback: {e}")
            ai_segment_decisions = None
    
    # Phase 1 Work Item 3: Build segments using strict JSON AI decisions or deterministic fallback
    segments = []
    current_time = 0.0

    # Build lookup from AI decisions by asset_index for efficient access
    ai_decisions_by_index = {}
    if ai_segment_decisions:
        for decision in ai_segment_decisions:
            asset_idx = decision.get("asset_index")
            if asset_idx is not None:
                ai_decisions_by_index[asset_idx] = decision

    for idx, asset in enumerate(selected_assets):
        media_type = asset["media_type"]
        role = asset["role"]

        # Phase 1 Work Item 3: Get duration and creative decisions from AI JSON or use deterministic fallback
        ai_decision = ai_decisions_by_index.get(idx)

        if ai_decision:
            # Use AI's strict JSON decisions
            duration = ai_decision.get("duration", 3.0)
            ai_transition = ai_decision.get("transition")
            ai_effect_notes = ai_decision.get("effect_notes", "")
            ai_overlay_text = ai_decision.get("overlay_text", "")
            ai_planned = True
        else:
            # Deterministic fallback based on role
            if role == "intro":
                duration = base_segment_duration * 1.2
                ai_transition = None
            elif role == "outro":
                duration = base_segment_duration * 1.0
                ai_transition = None
            else:
                duration = base_segment_duration
                ai_transition = None

            # Videos can be shorter
            if media_type == "video":
                duration = min(duration, 4.0)

            ai_effect_notes = ""
            ai_overlay_text = ""
            ai_planned = False

        duration = _clamp_segment_duration(asset, duration, len(selected_assets), target_duration)

        # Ensure we don't exceed target duration
        if current_time + duration > target_duration:
            duration = target_duration - current_time
            if duration < 1.0:
                break

        # Phase 1 Work Item 3: Determine transition (AI decision > user style > template default)
        if idx == 0:
            # First segment: use AI transition if valid, otherwise fade_in or hard_cut based on style
            if ai_transition and ai_transition in ["hard_cut", "fade_in"]:
                transition = ai_transition
            elif effective_transition == "hard_cut":
                transition = "hard_cut"
            else:
                transition = "fade_in"
        else:
            # Subsequent segments: AI transition if valid, otherwise effective_transition
            valid_transitions = ["hard_cut", "crossfade", "fade", "fade_in"]
            if ai_transition and ai_transition in valid_transitions:
                transition = ai_transition
            else:
                transition = effective_transition
        
        # Phase 1 Work Item 3: Build overlay text - use AI overlay if provided, otherwise FINAL CTA ONLY
        is_final_segment = (idx == len(selected_assets) - 1)

        # Use AI overlay text if provided and valid, otherwise use standard CTA on final segment
        if ai_overlay_text and len(ai_overlay_text) <= 50:
            overlay = {
                "text": ai_overlay_text,
                "position": "bottom" if is_final_segment else "center",
                "style": "cta" if is_final_segment else "hook",
                "duration": min(2.0, duration * 0.5)
            }
        else:
            overlay = _generate_segment_overlay(role, asset, template_key, idx, None, is_final_segment)

        # Phase 1 Work Item 3: Build effects with AI effect notes if available
        effects = _get_segment_effects(media_type, role, template_key)
        if ai_effect_notes:
            effects["ai_notes"] = ai_effect_notes

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
            "effects": effects,
            "ai_planned": ai_planned
        }
        
        segments.append(segment)
        current_time += duration
        
        if current_time >= target_duration:
            break

    _ensure_minimum_reel_duration(segments, selected_assets, target_duration)

    # Validate total duration
    total_duration = sum(s["duration"] for s in segments)

    # Build enhanced segments with complete source metadata
    enhanced_segments = []
    for idx, seg in enumerate(segments):
        asset = selected_assets[idx] if idx < len(selected_assets) else {}
        analysis = asset.get("analysis", {})
        advanced = analysis.get("advanced_analysis", {})

        enhanced_seg = {
            # Core segment info
            "segment_id": seg["segment_id"],
            "asset_id": seg["asset_id"],
            "source_path": seg["source_path"],
            "media_type": seg["media_type"],
            "role": seg["role"],
            "start_time": seg["start_time"],
            "duration": seg["duration"],
            "transition": seg["transition"],
            "overlay": seg["overlay"],
            "effects": seg["effects"],
            "ai_planned": seg.get("ai_planned", False),
            # Source metadata for renderer contract
            "source_metadata": {
                "file_exists": Path(seg["source_path"]).exists(),
                "media_type": seg["media_type"],
                "role": seg["role"],
                "analysis_summary": {
                    "hook_strength": advanced.get("hook_strength", 0),
                    "food_clarity": advanced.get("food_clarity", 0),
                    "motion_quality": advanced.get("motion_quality", 0),
                    "lighting_score": advanced.get("lighting_score", 0),
                    "orientation_fit": advanced.get("orientation_fit", 0.7),
                    "overall_score": analysis.get("reel_suitability", {}).get("score", 0.5)
                },
                "selection_reason": asset.get("selection_reason", "Selected by director"),
                "selection_source": asset.get("selection_source", "deterministic")
            }
        }
        enhanced_segments.append(enhanced_seg)

    # Build selection rationale (selected vs skipped)
    selection_rationale = {
        "selected_count": len(selected_assets),
        "selected_asset_ids": [s["asset_id"] for s in selected_assets],
        "selection_strategy": selected_assets[0].get("selection_strategy", "deterministic_scoring") if selected_assets else "none",
        "skipped_assets": []
    }

    # Add skipped asset info if all_assets provided
    if all_assets:
        selected_ids = {s["asset_id"] for s in selected_assets}
        for asset in all_assets:
            asset_id = asset["id"]
            if asset_id not in selected_ids:
                analysis = asset.get("analysis_json", {})
                advanced = analysis.get("advanced_analysis", {})
                skip_entry = {
                    "asset_id": asset_id,
                    "reason": advanced.get("skip_reason", "Not selected by director"),
                    "duplicate_of": advanced.get("duplicate_of"),
                    "disqualified": analysis.get("reel_suitability", {}).get("disqualified", False)
                }
                selection_rationale["skipped_assets"].append(skip_entry)

    # Generate edit plan with schema versioning (Phase 3)
    edit_plan = {
        # Schema versioning for contract stability
        "plan_schema_version": "1.0.0",
        "plan_id": f"plan_{uuid.uuid4().hex[:12]}",
        "project_id": project_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),

        # Target specifications
        "template_key": template_key,
        "target_duration": target_duration,
        "actual_duration": round(total_duration, 2),
        "duration_tolerance_seconds": 2.0,
        "segment_count": len(enhanced_segments),

        # Segments with complete source metadata
        "segments": enhanced_segments,

        # Selection rationale
        "selection_rationale": selection_rationale,

        # Global render settings (renderer contract)
        "global_settings": {
            "output_resolution": "1080x1920",
            "frame_rate": 30,
            "video_codec": "libx264",
            "audio_codec": "aac",
            "pixel_format": "yuv420p",
            "transition_duration": 0.5,
            "transition_style": transition_style,
            "effective_transition": effective_transition,
            "visual_filter": visual_filter,
            "supported_filters": ["none", "natural", "warm", "rich", "fresh"],
            "supported_transitions": ["hard_cut", "crossfade", "fade", "fade_in"]
        },

        # Validation metadata
        "validation": {
            "validated": False,  # Will be set by validate_edit_plan
            "validation_timestamp": None,
            "validation_errors": [],
            "duration_within_tolerance": abs(total_duration - target_duration) <= 2.0,
            "total_duration_seconds": round(total_duration, 2)
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
    Phase 3: Enhanced validation of edit plan as renderer contract.
    Returns (is_valid, error_message)

    Validates:
    - Schema version compatibility
    - Required fields presence
    - Segment integrity (asset_id, source_path, duration, transition)
    - Source file existence
    - Total duration within tolerance
    - Renderer-supported fields only
    """
    validation_errors = []
    is_valid = True

    # Check schema version (Phase 3)
    schema_version = edit_plan.get("plan_schema_version")
    if not schema_version:
        validation_errors.append("Missing plan_schema_version")
        is_valid = False
    elif schema_version != "1.0.0":
        # Future: handle version migration
        validation_errors.append(f"Schema version {schema_version} may require migration")

    # Check required fields
    required = ["plan_id", "project_id", "segments", "target_duration", "actual_duration", "global_settings"]
    for field in required:
        if field not in edit_plan:
            validation_errors.append(f"Missing required field: {field}")
            is_valid = False

    segments = edit_plan.get("segments", [])
    if not segments:
        validation_errors.append("No segments in edit plan")
        is_valid = False

    # Validate each segment
    supported_transitions = edit_plan.get("global_settings", {}).get("supported_transitions", ["hard_cut", "crossfade", "fade", "fade_in"])
    for idx, seg in enumerate(segments):
        if "asset_id" not in seg:
            validation_errors.append(f"Segment {idx}: missing asset_id")
            is_valid = False
        if "source_path" not in seg:
            validation_errors.append(f"Segment {idx}: missing source_path")
            is_valid = False
        if "duration" not in seg or seg["duration"] <= 0:
            validation_errors.append(f"Segment {idx}: invalid duration")
            is_valid = False
        if "transition" not in seg:
            validation_errors.append(f"Segment {idx}: missing transition")
            is_valid = False
        elif seg.get("transition") not in supported_transitions:
            validation_errors.append(f"Segment {idx}: unsupported transition '{seg.get('transition')}'")
            is_valid = False

        # Check source file exists
        if not Path(seg["source_path"]).exists():
            validation_errors.append(f"Segment {idx}: source file not found: {seg.get('source_path', 'unknown')}")
            is_valid = False

    # Check total duration
    total = sum(s["duration"] for s in segments)
    target = edit_plan.get("target_duration", 30)
    tolerance = edit_plan.get("duration_tolerance_seconds", 2.0)

    if total > target + tolerance:
        validation_errors.append(f"Total duration ({total:.1f}s) exceeds target ({target}s) + tolerance ({tolerance}s)")
        is_valid = False

    # Short plans (< 30s) are padded to 30s by the renderer via tpad — not a hard failure
    if total < 3:
        validation_errors.append(f"Total duration ({total:.1f}s) too short — need at least 3 seconds of content")
        is_valid = False

    # Update validation metadata in edit_plan (Phase 3)
    validation_meta = edit_plan.get("validation", {})
    validation_meta["validated"] = is_valid
    validation_meta["validation_timestamp"] = datetime.now(timezone.utc).isoformat()
    validation_meta["validation_errors"] = validation_errors
    validation_meta["duration_within_tolerance"] = abs(total - target) <= tolerance
    validation_meta["total_duration_seconds"] = round(total, 2)
    edit_plan["validation"] = validation_meta

    error_msg = "; ".join(validation_errors) if validation_errors else None
    return is_valid, error_msg


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
