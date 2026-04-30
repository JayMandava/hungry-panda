"""
Reels Maker - Phase 3: Rendering
FFmpeg-based video rendering pipeline
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_RENDER_SUPPORT = True
except ImportError:
    HEIF_RENDER_SUPPORT = False

from infra.config.logging_config import logger
from infra.config.settings import config


@dataclass
class RenderResult:
    """Result of a render operation"""
    success: bool
    output_path: Optional[str]
    error_message: Optional[str]
    duration: float
    diagnostics: Dict[str, Any]


class FFmpegRenderer:
    """
    Renders Instagram Reels using ffmpeg.
    Supports images (Ken Burns), videos (trim/scale), text overlays, and transitions.
    """
    
    # Target specs for Instagram Reels
    TARGET_WIDTH = 1080
    TARGET_HEIGHT = 1920
    TARGET_FPS = 30
    TARGET_CODEC = "libx264"
    TARGET_AUDIO_CODEC = "aac"
    TARGET_PIXEL_FORMAT = "yuv420p"
    
    # Visual filter presets (deterministic ffmpeg filter chains)
    FILTER_PRESETS = {
        "none": "",  # No filter applied
        "natural": "eq=contrast=1.0:saturation=1.0:brightness=0.0",  # Neutral, true-to-life
        "warm": "eq=contrast=1.05:saturation=1.1:brightness=0.02,curves=r='0.0/0.0 0.5/0.52 1.0/1.0':g='0.0/0.0 0.5/0.48 1.0/1.0'",  # Warmer tones
        "rich": "eq=contrast=1.15:saturation=1.2:brightness=-0.02,curves=r='0.0/0.0 0.5/0.48 1.0/1.0':g='0.0/0.0 0.5/0.50 1.0/1.0':b='0.0/0.0 0.5/0.52 1.0/1.0'",  # Higher contrast, richer
        "fresh": "eq=contrast=1.0:saturation=1.15:brightness=0.03,curves=r='0.0/0.0 0.5/0.46 1.0/1.0':g='0.0/0.0 0.5/0.52 1.0/1.0':b='0.0/0.0 0.5/0.54 1.0/1.0'",  # Bright, vibrant
    }
    
    def __init__(self, temp_dir: Optional[Path] = None, visual_filter: str = "none"):
        self.temp_dir = temp_dir or Path(tempfile.gettempdir())
        self.visual_filter = visual_filter if visual_filter in self.FILTER_PRESETS else "none"
        self._check_ffmpeg()
    
    def _get_visual_filter(self) -> str:
        """Get the ffmpeg filter string for the current visual filter preset."""
        return self.FILTER_PRESETS.get(self.visual_filter, "")
    
    def _check_ffmpeg(self):
        """Verify ffmpeg is available"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                raise RuntimeError("ffmpeg not working properly")
        except FileNotFoundError:
            raise RuntimeError("ffmpeg not found. Please install ffmpeg.")
    
    def render_reel(self, edit_plan: Dict[str, Any], output_path: str, visual_filter: Optional[str] = None) -> RenderResult:
        """
        Phase 3: Render a complete reel from edit plan.
        Returns RenderResult with output path or error.

        Consumes the full edit_plan contract including:
        - segments with source_metadata and transitions
        - global_settings (visual_filter, transition_style, output specs)
        - validation metadata

        Args:
            edit_plan: The edit plan with segments to render (Phase 3 schema v1.0.0)
            output_path: Path for the final output video
            visual_filter: Optional override for visual filter (none, natural, warm, rich, fresh)
        """
        # Phase 3: Read visual_filter from edit_plan if not provided as override
        if visual_filter and visual_filter in self.FILTER_PRESETS:
            self.visual_filter = visual_filter
            logger.info(f"Using visual filter (override): {visual_filter}")
        else:
            # Read from edit_plan global_settings (Phase 3 contract)
            global_settings = edit_plan.get("global_settings", {})
            plan_filter = global_settings.get("visual_filter")
            if plan_filter and plan_filter in self.FILTER_PRESETS:
                self.visual_filter = plan_filter
                logger.info(f"Using visual filter from edit_plan: {plan_filter}")
            elif plan_filter:
                logger.warning(f"Visual filter '{plan_filter}' from edit_plan not supported, using 'none'")
                self.visual_filter = "none"
        
        segments = edit_plan.get("segments", [])
        if not segments:
            return RenderResult(
                success=False,
                output_path=None,
                error_message="No segments in edit plan",
                duration=0,
                diagnostics={}
            )
        
        temp_files = []
        diagnostics = {
            "segments_rendered": 0,
            "total_segments": len(segments),
            "temp_files_created": [],
            "ffmpeg_commands": []
        }
        
        try:
            # Step 1: Render individual segments
            segment_files = []
            for idx, segment in enumerate(segments):
                logger.info(f"Rendering segment {idx+1}/{len(segments)}: {segment.get('role', 'body')}")
                
                temp_segment = self.temp_dir / f"segment_{idx}_{os.urandom(4).hex()}.mp4"
                temp_files.append(temp_segment)
                
                success = self._render_segment(segment, str(temp_segment), diagnostics)
                if success:
                    segment_files.append(str(temp_segment))
                    diagnostics["segments_rendered"] += 1
                else:
                    logger.warning(f"Failed to render segment {idx}, continuing with remaining")
            
            if not segment_files:
                return RenderResult(
                    success=False,
                    output_path=None,
                    error_message="All segments failed to render",
                    duration=0,
                    diagnostics=diagnostics
                )
            
            # Step 2: Concatenate segments with transitions
            logger.info(f"Concatenating {len(segment_files)} segments with transitions")
            
            # Build segment info with transitions for proper rendering
            segment_info = []
            for idx, segment in enumerate(segments):
                if idx < len(segment_files):
                    segment_info.append({
                        "file": segment_files[idx],
                        "transition": segment.get("transition", "hard_cut"),
                        "duration": segment.get("duration", 3.0)
                    })
            
            concat_success = self._concatenate_with_transitions(segment_info, output_path, diagnostics)
            
            if not concat_success:
                return RenderResult(
                    success=False,
                    output_path=None,
                    error_message="Failed to concatenate segments",
                    duration=0,
                    diagnostics=diagnostics
                )
            
            # Step 3: Final normalization (add audio, enforce 30s minimum duration)
            logger.info("Normalizing final output with audio and duration enforcement")
            temp_normalized = self.temp_dir / f"normalized_{os.urandom(4).hex()}.mp4"
            temp_files.append(temp_normalized)
            
            target_duration = edit_plan.get("target_duration", 30.0)
            normalize_success = self._normalize_final_output(
                output_path, 
                str(temp_normalized), 
                target_duration,
                diagnostics
            )
            
            if normalize_success:
                # Replace original with normalized version
                import shutil
                shutil.move(str(temp_normalized), output_path)
            else:
                logger.warning("Final normalization failed, proceeding with unnormalized output")
            
            # Step 4: Validate output contract
            logger.info("Validating output contract")
            is_valid, validation_diagnostics = self.validate_output_contract(output_path)
            diagnostics["validation"] = validation_diagnostics
            
            if not is_valid:
                logger.error(f"Output validation failed: {validation_diagnostics['errors']}")
                # Still return success but with warning - let caller decide
                diagnostics["validation_warnings"] = validation_diagnostics['errors']
            else:
                logger.info("Output validation passed")
            
            # Step 5: Get final duration
            duration = self._get_video_duration(output_path)
            diagnostics["final_duration"] = duration
            
            return RenderResult(
                success=True,
                output_path=output_path,
                error_message=None if is_valid else f"Validation warnings: {validation_diagnostics['errors']}",
                duration=duration,
                diagnostics=diagnostics
            )
            
        except Exception as e:
            logger.error(f"Render failed: {e}")
            return RenderResult(
                success=False,
                output_path=None,
                error_message=str(e),
                duration=0,
                diagnostics=diagnostics
            )
        finally:
            # Cleanup temp files
            for temp_file in temp_files:
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                except:
                    pass
    
    def _render_segment(self, segment: Dict, output_path: str, diagnostics: Dict) -> bool:
        """Render a single segment (image or video)"""
        media_type = segment.get("media_type")
        source_path = segment.get("source_path")
        duration = segment.get("duration", 3.0)
        effects = segment.get("effects", {})
        overlay = segment.get("overlay", {})
        
        if not source_path or not Path(source_path).exists():
            logger.error(f"Source file not found: {source_path}")
            return False
        
        try:
            if media_type == "image":
                return self._render_image_segment(
                    source_path, output_path, duration, effects, overlay, diagnostics
                )
            elif media_type == "video":
                return self._render_video_segment(
                    source_path, output_path, duration, effects, overlay, diagnostics
                )
            else:
                logger.error(f"Unknown media type: {media_type}")
                return False
        except Exception as e:
            logger.error(f"Segment render failed: {e}")
            return False
    
    def _render_image_segment(
        self,
        source_path: str,
        output_path: str,
        duration: float,
        effects: Dict,
        overlay: Dict,
        diagnostics: Dict
    ) -> bool:
        """Render an image segment with Ken Burns effect"""
        render_source_path = source_path
        temp_image_path: Optional[Path] = None

        try:
            render_source_path, temp_image_path = self._prepare_image_render_source(source_path)
        except Exception as exc:
            logger.error(f"Image segment preparation failed for {source_path}: {exc}")
            return False
        
        # Ken Burns effect parameters
        ken_burns = effects.get("ken_burns", {})
        if ken_burns.get("enabled", True):
            zoom_start = ken_burns.get("zoom_start", 1.0)
            zoom_end = ken_burns.get("zoom_end", 1.15)
            pan_direction = ken_burns.get("pan_direction", "random")
        else:
            zoom_start = zoom_end = 1.0
            pan_direction = "none"
        
        # Build Ken Burns filter
        # Scale to fill 1080x1920 while maintaining aspect ratio (crop to fill)
        # Then apply zoom animation
        kb_filter = self._build_ken_burns_filter(zoom_start, zoom_end, duration, pan_direction)
        
        # Build visual filter if enabled
        visual_filter_str = self._get_visual_filter()
        
        # Build overlay filter if text present
        overlay_filter = ""
        text = overlay.get("text", "")
        if text:
            overlay_filter = self._build_text_overlay_filter(overlay, duration)
        
        # Combine filters: Ken Burns -> Visual Filter -> Overlay
        filters = [kb_filter]
        if visual_filter_str:
            filters.append(visual_filter_str)
        if overlay_filter:
            filters.append(overlay_filter)
        
        video_filter = ",".join(filters)
        
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', render_source_path,
            '-vf', video_filter,
            '-c:v', self.TARGET_CODEC,
            '-pix_fmt', self.TARGET_PIXEL_FORMAT,
            '-r', str(self.TARGET_FPS),
            '-t', str(duration),
            '-movflags', '+faststart',
            '-preset', 'fast',
            '-crf', '23',
            output_path
        ]
        
        diagnostics["ffmpeg_commands"].append(" ".join(cmd))
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=60
        )
        
        if result.returncode != 0:
            logger.error(f"Image segment render failed: {result.stderr.decode()[:500]}")
            if temp_image_path and temp_image_path.exists():
                temp_image_path.unlink(missing_ok=True)
            return False
        
        if temp_image_path and temp_image_path.exists():
            temp_image_path.unlink(missing_ok=True)
        return True

    def _prepare_image_render_source(self, source_path: str) -> Tuple[str, Optional[Path]]:
        """Convert image sources that ffmpeg may not decode reliably into a temporary JPEG."""
        source = Path(source_path)
        suffix = source.suffix.lower()

        if suffix not in {".heic", ".heif"}:
            return source_path, None

        if not HEIF_RENDER_SUPPORT:
            raise RuntimeError("HEIF render support unavailable on server")

        temp_image_path = self.temp_dir / f"render_{source.stem}_{os.urandom(4).hex()}.jpg"

        with Image.open(source) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            elif img.mode == "L":
                img = img.convert("RGB")
            img.save(temp_image_path, format="JPEG", quality=95)

        return str(temp_image_path), temp_image_path
    
    def _render_video_segment(
        self,
        source_path: str,
        output_path: str,
        duration: float,
        effects: Dict,
        overlay: Dict,
        diagnostics: Dict
    ) -> bool:
        """Render a video segment with trim and scale"""
        
        # Build scale/crop filter to 1080x1920 - crop to fill (no black bars)
        # force_original_aspect_ratio=increase scales so one dimension matches, then crop overflows
        scale_filter = (
            f"scale={self.TARGET_WIDTH}:{self.TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
            f"setsar=1:1,"
            f"crop={self.TARGET_WIDTH}:{self.TARGET_HEIGHT}:(iw-{self.TARGET_WIDTH})/2:(ih-{self.TARGET_HEIGHT})/2"
        )
        
        # Build visual filter if enabled
        visual_filter_str = self._get_visual_filter()
        
        # Build overlay filter if text present
        overlay_filter = ""
        text = overlay.get("text", "")
        if text:
            overlay_filter = self._build_text_overlay_filter(overlay, duration)
        
        # Combine filters: Scale -> Visual Filter -> Overlay
        filters = [scale_filter]
        if visual_filter_str:
            filters.append(visual_filter_str)
        if overlay_filter:
            filters.append(overlay_filter)
        
        video_filter = ",".join(filters)
        
        cmd = [
            'ffmpeg', '-y',
            '-i', source_path,
            '-vf', video_filter,
            '-c:v', self.TARGET_CODEC,
            '-pix_fmt', self.TARGET_PIXEL_FORMAT,
            '-r', str(self.TARGET_FPS),
            '-t', str(duration),
            '-movflags', '+faststart',
            '-preset', 'fast',
            '-crf', '23',
            '-an',  # No audio for now
            output_path
        ]
        
        diagnostics["ffmpeg_commands"].append(" ".join(cmd))
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=120
        )
        
        if result.returncode != 0:
            logger.error(f"Video segment render failed: {result.stderr.decode()[:500]}")
            return False
        
        return True
    
    def _build_ken_burns_filter(self, zoom_start: float, zoom_end: float, duration: float, pan_direction: str) -> str:
        """Build ffmpeg filter for Ken Burns effect"""
        
        # Base scale to fill 1080x1920
        base_scale = f"scale={self.TARGET_WIDTH}:{self.TARGET_HEIGHT}:force_original_aspect_ratio=increase"
        
        if zoom_start == zoom_end == 1.0:
            # No zoom, just scale to fill and crop (no black bars)
            return (
                f"{base_scale},"
                f"setsar=1:1,"
                f"crop={self.TARGET_WIDTH}:{self.TARGET_HEIGHT}:(iw-{self.TARGET_WIDTH})/2:(ih-{self.TARGET_HEIGHT})/2"
            )
        
        # Calculate pan direction
        if pan_direction == "random":
            import random
            pan_direction = random.choice(["left", "right", "up", "down", "center"])
        
        # Build zoompan filter
        # zoompan format: z='min(zoom)+...+zoom' with expression
        frames = int(duration * self.TARGET_FPS)
        
        # Zoom expression: linear interpolation from zoom_start to zoom_end
        zoom_expr = f"{zoom_start}+({zoom_end}-{zoom_start})*on/{frames}"
        
        # Pan coordinates based on direction
        if pan_direction == "left":
            x_expr = f"(iw-iw*{zoom_expr})*(1-on/{frames})"
            y_expr = f"(ih-ih*{zoom_expr})/2"
        elif pan_direction == "right":
            x_expr = f"(iw-iw*{zoom_expr})*(on/{frames})"
            y_expr = f"(ih-ih*{zoom_expr})/2"
        elif pan_direction == "up":
            x_expr = f"(iw-iw*{zoom_expr})/2"
            y_expr = f"(ih-ih*{zoom_expr})*(1-on/{frames})"
        elif pan_direction == "down":
            x_expr = f"(iw-iw*{zoom_expr})/2"
            y_expr = f"(ih-ih*{zoom_expr})*(on/{frames})"
        else:  # center
            x_expr = f"(iw-iw*{zoom_expr})/2"
            y_expr = f"(ih-ih*{zoom_expr})/2"
        
        # zoompan filter with output size
        zoompan = (
            f"zoompan=z='{zoom_expr}':"
            f"x='{x_expr}':"
            f"y='{y_expr}':"
            f"d={frames}:"
            f"s={self.TARGET_WIDTH}x{self.TARGET_HEIGHT}"
        )
        
        # Full filter chain
        return (
            f"{base_scale},"
            f"setsar=1:1,"
            f"{zoompan}"
        )
    
    def _build_text_overlay_filter(self, overlay: Dict, duration: float) -> str:
        """Build ffmpeg filter for text overlay"""
        text = overlay.get("text", "")
        if not text:
            return ""
        
        position = overlay.get("position", "center")
        style = overlay.get("style", "title")
        
        # Escape single quotes in text
        text = text.replace("'", "\\'")
        
        # Style settings
        if style == "title":
            font_size = 72
            font_color = "white"
            box = 1
            box_color = "black@0.5"
        elif style == "cta":
            font_size = 56
            font_color = "white"
            box = 1
            box_color = "#6e9a42@0.8"  # Brand green
        else:  # subtle
            font_size = 36
            font_color = "white"
            box = 0
            box_color = ""
        
        # Position coordinates
        if position == "center":
            x = "(w-text_w)/2"
            y = "(h-text_h)/2"
        elif position == "bottom":
            x = "(w-text_w)/2"
            y = "h-text_h-100"
        else:
            x = "(w-text_w)/2"
            y = "h-text_h-50"
        
        # Build drawtext filter
        drawtext = (
            f"drawtext=text='{text}':"
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"fontsize={font_size}:"
            f"fontcolor={font_color}:"
            f"x={x}:"
            f"y={y}"
        )
        
        if box:
            drawtext += f":box=1:boxcolor={box_color}:boxborderw=10"
        
        return drawtext
    
    def _concatenate_segments(self, segment_files: List[str], output_path: str, diagnostics: Dict) -> bool:
        """Concatenate multiple segment files into final output"""
        
        if len(segment_files) == 1:
            # Single segment, just copy
            cmd = [
                'ffmpeg', '-y',
                '-i', segment_files[0],
                '-c', 'copy',
                '-movflags', '+faststart',
                output_path
            ]
        else:
            # Multiple segments - use concat demuxer
            # Create concat file list
            concat_file = self.temp_dir / f"concat_{os.urandom(4).hex()}.txt"
            with open(concat_file, 'w') as f:
                for seg_path in segment_files:
                    f.write(f"file '{seg_path}'\n")
            
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',
                '-movflags', '+faststart',
                output_path
            ]
            
            diagnostics["temp_files_created"].append(str(concat_file))
        
        diagnostics["ffmpeg_commands"].append(" ".join(cmd))
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=120
        )
        
        # Cleanup concat file
        if 'concat_file' in locals() and concat_file.exists():
            try:
                concat_file.unlink()
            except:
                pass
        
        if result.returncode != 0:
            logger.error(f"Concatenation failed: {result.stderr.decode()[:500]}")
            return False
        
        return True
    
    def _concatenate_with_transitions(self, segment_info: List[Dict], output_path: str, diagnostics: Dict) -> bool:
        """
        Concatenate segments with real transitions using ffmpeg filter_complex.
        Supports: hard_cut (plain join), crossfade/xfade (smooth transitions)
        """
        if len(segment_info) == 1:
            # Single segment, just copy
            cmd = [
                'ffmpeg', '-y',
                '-i', segment_info[0]["file"],
                '-c', 'copy',
                '-movflags', '+faststart',
                output_path
            ]
            diagnostics["ffmpeg_commands"].append(" ".join(cmd))
            
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            return result.returncode == 0
        
        # Check if all transitions are hard_cut (use simple concat)
        all_hard_cut = all(seg.get("transition") == "hard_cut" for seg in segment_info)
        if all_hard_cut:
            logger.info("All segments use hard_cut - using simple concat demuxer")
            segment_files = [s["file"] for s in segment_info]
            return self._concatenate_segments(segment_files, output_path, diagnostics)
        
        # Multiple segments with smooth transitions - use filter_complex with xfade
        try:
            transition_duration = 0.5  # 0.5 second transitions
            
            # Build input files and filter_complex
            inputs = []
            filter_parts = []
            
            for idx, seg in enumerate(segment_info):
                inputs.extend(['-i', seg["file"]])
            
            # Build filter_complex for xfade transitions
            # Format: [0:v][1:v]xfade=transition=fade:duration=0.5:offset=2.5[vt1];
            # [vt1][2:v]xfade=transition=fade:duration=0.5:offset=5.0[vt2]...
            
            current_offset = segment_info[0]["duration"] - transition_duration
            filter_chain = []
            
            for i in range(len(segment_info) - 1):
                transition = segment_info[i].get("transition", "hard_cut")
                
                # Map transition names to xfade transition types
                xfade_transition = self._map_transition_type(transition)
                
                if i == 0:
                    # First transition: [0:v][1:v] -> [vt1]
                    filter_chain.append(
                        f"[{i}:v][{i+1}:v]xfade=transition={xfade_transition}:"
                        f"duration={transition_duration}:offset={current_offset}[vt{i}]"
                    )
                else:
                    # Subsequent: [vt{i-1}][{i+1}:v] -> [vt{i}]
                    prev_label = f"vt{i-1}" if i > 1 else "vt0"
                    filter_chain.append(
                        f"[{prev_label}][{i+1}:v]xfade=transition={xfade_transition}:"
                        f"duration={transition_duration}:offset={current_offset}[vt{i}]"
                    )
                
                # Update offset for next transition (subtract overlap)
                if i < len(segment_info) - 2:
                    current_offset += segment_info[i+1]["duration"] - transition_duration
            
            # Build final filter string
            video_filter = ";".join(filter_chain)
            final_video_label = f"vt{len(segment_info)-2}" if len(segment_info) > 2 else "vt0"
            
            # Add format and output
            video_filter += f";[{final_video_label}]format=yuv420p[final]"
            
            cmd = [
                'ffmpeg', '-y',
                *inputs,
                '-filter_complex', video_filter,
                '-map', '[final]',
                '-c:v', self.TARGET_CODEC,
                '-pix_fmt', self.TARGET_PIXEL_FORMAT,
                '-r', str(self.TARGET_FPS),
                '-movflags', '+faststart',
                '-preset', 'fast',
                '-crf', '23',
                output_path
            ]
            
            diagnostics["ffmpeg_commands"].append(" ".join(cmd))
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=180  # Longer timeout for complex filter
            )
            
            if result.returncode != 0:
                stderr = result.stderr.decode()
                logger.error(f"Transition concatenation failed: {stderr[:500]}")
                
                # Fallback: try simple concat without transitions
                logger.info("Falling back to simple concat without transitions")
                segment_files = [s["file"] for s in segment_info]
                return self._concatenate_segments(segment_files, output_path, diagnostics)
            
            return True
            
        except Exception as e:
            logger.error(f"Transition rendering failed: {e}")
            # Fallback to simple concat
            try:
                segment_files = [s["file"] for s in segment_info]
                return self._concatenate_segments(segment_files, output_path, diagnostics)
            except:
                return False
    
    def _map_transition_type(self, transition: str) -> str:
        """Map template transition names to xfade transition types"""
        transition_map = {
            "hard_cut": "fade",  # xfade doesn't have hard cut, use minimal fade
            "crossfade": "fade",
            "fade": "fade",
            "fade_in": "fade",
            "smooth": "fade",
            "zoom": "fade",  # Degrade zoom to fade as specified
        }
        return transition_map.get(transition, "fade")
    
    def _get_video_duration(self, video_path: str) -> float:
        """Get duration of rendered video"""
        try:
            result = subprocess.run(
                [
                    'ffprobe', '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    video_path
                ],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                return float(result.stdout.decode().strip())
        except:
            pass
        return 0.0
    
    def generate_poster_frame(self, video_path: str, output_path: str, timestamp: float = 1.0) -> bool:
        """Extract a poster frame from the rendered video"""
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-ss', str(timestamp),
                '-vframes', '1',
                '-q:v', '2',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Poster generation failed: {e}")
            return False


    def _normalize_final_output(
        self, 
        input_path: str, 
        output_path: str, 
        target_duration: float,
        diagnostics: Dict
    ) -> bool:
        """
        Normalize final output to Instagram-safe format.
        - Ensures 30-60s duration (extends if needed)
        - Adds AAC audio track (silent if no audio)
        - Re-encodes to H.264/AAC with proper settings
        """
        # First, check actual duration
        duration = self._get_video_duration(input_path)
        
        # Calculate extension needed
        if duration and duration < 30.0:
            # Need to extend - use tpad for video and add silent audio
            # Input has no audio (rendered with -an), so use anullsrc
            pad_duration = 30.0 - duration
            
            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-f', 'lavfi', '-i', f'anullsrc=r=44100:cl=stereo:d={pad_duration + duration}',  # Silent audio for full duration
                '-filter_complex',
                f'[0:v]tpad=stop_mode=clone:stop_duration={pad_duration}[v]',
                '-map', '[v]',
                '-map', '1:a',  # Use audio from anullsrc
                '-c:v', self.TARGET_CODEC,
                '-pix_fmt', self.TARGET_PIXEL_FORMAT,
                '-r', str(self.TARGET_FPS),
                '-c:a', self.TARGET_AUDIO_CODEC,
                '-b:a', '128k',
                '-ar', '44100',
                '-movflags', '+faststart',
                '-preset', 'fast',
                '-crf', '23',
                '-shortest',
                output_path
            ]
        else:
            # Duration OK or unknown - just add audio if missing and normalize
            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',  # Silent audio source
                '-c:v', self.TARGET_CODEC,
                '-pix_fmt', self.TARGET_PIXEL_FORMAT,
                '-r', str(self.TARGET_FPS),
                '-c:a', self.TARGET_AUDIO_CODEC,
                '-b:a', '128k',
                '-ar', '44100',
                '-shortest',  # Match audio to video duration
                '-movflags', '+faststart',
                '-preset', 'fast',
                '-crf', '23',
                output_path
            ]
        
        diagnostics["ffmpeg_commands"].append(" ".join(cmd))
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=120
        )
        
        if result.returncode != 0:
            logger.error(f"Final normalization failed: {result.stderr.decode()[:500]}")
            return False
        
        return True

    def validate_output_contract(self, output_path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate final output meets Instagram contract using ffprobe.
        Returns (is_valid, diagnostics_dict)
        """
        import json
        
        diagnostics = {
            "file": output_path,
            "valid": False,
            "errors": [],
            "streams": {},
        }
        
        if not Path(output_path).exists():
            diagnostics["errors"].append("File does not exist")
            return False, diagnostics
        
        # Run ffprobe
        cmd = [
            'ffprobe', '-v', 'error',
            '-print_format', 'json',
            '-show_streams',
            '-show_format',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        
        if result.returncode != 0:
            diagnostics["errors"].append(f"ffprobe failed: {result.stderr.decode()[:200]}")
            return False, diagnostics
        
        try:
            probe_data = json.loads(result.stdout.decode())
        except json.JSONDecodeError as e:
            diagnostics["errors"].append(f"Failed to parse ffprobe output: {e}")
            return False, diagnostics
        
        streams = probe_data.get("streams", [])
        format_info = probe_data.get("format", {})
        
        # Analyze streams
        video_stream = None
        audio_stream = None
        
        for stream in streams:
            if stream.get("codec_type") == "video":
                video_stream = stream
            elif stream.get("codec_type") == "audio":
                audio_stream = stream
        
        # Validate video stream
        if not video_stream:
            diagnostics["errors"].append("No video stream found")
        else:
            diagnostics["streams"]["video"] = {
                "codec": video_stream.get("codec_name"),
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
                "pix_fmt": video_stream.get("pix_fmt"),
                "fps": eval(video_stream.get("r_frame_rate", "0/1")),  # e.g., "30/1"
            }
            
            # Check video specs
            if video_stream.get("codec_name") != "h264":
                diagnostics["errors"].append(f"Video codec is {video_stream.get('codec_name')}, expected h264")
            
            if video_stream.get("width") != self.TARGET_WIDTH or video_stream.get("height") != self.TARGET_HEIGHT:
                diagnostics["errors"].append(
                    f"Resolution is {video_stream.get('width')}x{video_stream.get('height')}, "
                    f"expected {self.TARGET_WIDTH}x{self.TARGET_HEIGHT}"
                )
            
            if video_stream.get("pix_fmt") != self.TARGET_PIXEL_FORMAT:
                diagnostics["errors"].append(
                    f"Pixel format is {video_stream.get('pix_fmt')}, expected {self.TARGET_PIXEL_FORMAT}"
                )
        
        # Validate audio stream
        if not audio_stream:
            diagnostics["errors"].append("No audio stream found (AAC required)")
        else:
            diagnostics["streams"]["audio"] = {
                "codec": audio_stream.get("codec_name"),
                "sample_rate": audio_stream.get("sample_rate"),
            }
            
            if audio_stream.get("codec_name") != "aac":
                diagnostics["errors"].append(f"Audio codec is {audio_stream.get('codec_name')}, expected aac")
        
        # Validate duration
        duration_str = format_info.get("duration")
        if duration_str:
            try:
                duration = float(duration_str)
                diagnostics["duration_seconds"] = duration
                
                if duration < 30.0:
                    diagnostics["errors"].append(f"Duration is {duration:.2f}s, minimum is 30s")
                elif duration > 60.0:
                    diagnostics["errors"].append(f"Duration is {duration:.2f}s, maximum is 60s")
            except ValueError:
                diagnostics["errors"].append(f"Could not parse duration: {duration_str}")
        else:
            diagnostics["errors"].append("Could not determine duration")
        
        # Format info
        diagnostics["format"] = {
            "format_name": format_info.get("format_name"),
            "bit_rate": format_info.get("bit_rate"),
        }
        
        is_valid = len(diagnostics["errors"]) == 0
        diagnostics["valid"] = is_valid
        
        return is_valid, diagnostics


# Convenience function
def render_reel_from_plan(edit_plan: Dict[str, Any], output_path: str) -> RenderResult:
    """Render a reel from edit plan to output file"""
    renderer = FFmpegRenderer()
    return renderer.render_reel(edit_plan, output_path)
