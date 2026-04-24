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

from config.logging_config import logger
from config.settings import config


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
    
    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or Path(tempfile.gettempdir())
        self._check_ffmpeg()
    
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
    
    def render_reel(self, edit_plan: Dict[str, Any], output_path: str) -> RenderResult:
        """
        Render a complete reel from edit plan.
        Returns RenderResult with output path or error.
        """
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
            
            # Step 3: Get final duration
            duration = self._get_video_duration(output_path)
            
            return RenderResult(
                success=True,
                output_path=output_path,
                error_message=None,
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
        
        # Build overlay filter if text present
        overlay_filter = ""
        text = overlay.get("text", "")
        if text:
            overlay_filter = self._build_text_overlay_filter(overlay, duration)
        
        # Combine filters
        if overlay_filter:
            video_filter = f"{kb_filter},{overlay_filter}"
        else:
            video_filter = kb_filter
        
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
        
        # Build overlay filter if text present
        overlay_filter = ""
        text = overlay.get("text", "")
        if text:
            overlay_filter = self._build_text_overlay_filter(overlay, duration)
        
        if overlay_filter:
            video_filter = f"{scale_filter},{overlay_filter}"
        else:
            video_filter = scale_filter
        
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


# Convenience function
def render_reel_from_plan(edit_plan: Dict[str, Any], output_path: str) -> RenderResult:
    """Render a reel from edit plan to output file"""
    renderer = FFmpegRenderer()
    return renderer.render_reel(edit_plan, output_path)
