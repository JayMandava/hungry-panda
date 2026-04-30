"""
Remotion Renderer - Phase 5 Spike
Alternative renderer using Remotion (React + WebCodecs) behind feature flag.

Consumes the same edit_plan contract as FFmpegRenderer:
- schema_version: "1.0.0"
- segments with source_metadata
- global_settings with visual_filter, transition_style
- target_duration enforcement
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import shutil

from infra.config.logging_config import logger
from infra.config.settings import config


@dataclass
class RemotionRenderResult:
    """Result of a Remotion render operation"""
    success: bool
    output_path: Optional[str]
    error_message: Optional[str]
    duration: float
    diagnostics: Dict[str, Any]


class RemotionRenderer:
    """
    Phase 5: Remotion-based renderer for Instagram Reels.
    
    Uses Remotion CLI to render React compositions that consume the edit_plan.
    Provides same interface as FFmpegRenderer for feature-flag swapping.
    
    Requirements:
    - Node.js 18+
    - npm dependencies installed in remotion/ directory
    """
    
    TARGET_WIDTH = 1080
    TARGET_HEIGHT = 1920
    TARGET_FPS = 30
    
    def __init__(self, remotion_dir: Optional[Path] = None, output_dir: Optional[Path] = None):
        self.remotion_dir = remotion_dir or Path(__file__).parent.parent.parent / "remotion"
        self.output_dir = output_dir or Path(config.REMOTION_OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._check_prerequisites()
    
    def _check_prerequisites(self):
        """Verify Node.js and npm are available"""
        try:
            # Check Node.js
            result = subprocess.run(
                ['node', '--version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                raise RuntimeError("Node.js not working properly")
            
            node_version = result.stdout.decode().strip()
            logger.info(f"Node.js version: {node_version}")
            
            # Check npm
            result = subprocess.run(
                ['npm', '--version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                raise RuntimeError("npm not found")
            
            # Check if node_modules exists
            node_modules = self.remotion_dir / "node_modules"
            if not node_modules.exists():
                logger.warning(f"Remotion dependencies not installed. Run: cd {self.remotion_dir} && npm install")
                
        except FileNotFoundError as e:
            raise RuntimeError(f"Prerequisite not found: {e}")
    
    def render_reel(self, edit_plan: Dict[str, Any], output_path: str) -> RemotionRenderResult:
        """
        Render a reel using Remotion CLI.
        
        Args:
            edit_plan: The edit plan with segments to render (Phase 3 schema v1.0.0)
            output_path: Path for the final output video
            
        Returns:
            RemotionRenderResult with output path or error
        """
        diagnostics = {
            "remotion_dir": str(self.remotion_dir),
            "output_path": output_path,
            "temp_files": [],
            "commands_run": []
        }
        
        temp_input_file = None
        
        try:
            # Step 1: Prepare edit plan for Remotion
            # Remotion expects public/ directory for static files
            remotion_public = self.remotion_dir / "public"
            remotion_public.mkdir(exist_ok=True)
            
            # Step 2: Write edit plan as input props
            temp_input_file = tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.json',
                delete=False,
                dir=str(remotion_public)
            )
            
            # Transform edit plan for Remotion consumption
            remotion_props = self._transform_edit_plan_for_remotion(edit_plan)
            json.dump(remotion_props, temp_input_file, indent=2)
            temp_input_file.close()
            diagnostics["temp_files"].append(temp_input_file.name)
            
            # Step 3: Calculate duration in frames
            target_duration = edit_plan.get("target_duration", 30.0)
            duration_in_frames = int(target_duration * self.TARGET_FPS)
            
            # Ensure minimum 30 seconds (Instagram requirement)
            min_frames = 30 * self.TARGET_FPS
            if duration_in_frames < min_frames:
                logger.warning(f"Duration {duration_in_frames} frames below minimum, extending to {min_frames}")
                duration_in_frames = min_frames
            
            # Step 4: Build Remotion render command
            input_props_path = temp_input_file.name
            output_filename = Path(output_path).name
            remotion_output = self.output_dir / output_filename
            
            # Create symlink or copy for static files if needed
            self._prepare_static_assets(edit_plan, remotion_public)
            
            # Run Remotion CLI render
            cmd = [
                'npx', 'remotion', 'render',
                'ReelComposition',
                str(remotion_output),
                '--props', input_props_path,
                '--codec', 'h264',
                '--fps', str(self.TARGET_FPS),
                '--duration-in-frames', str(duration_in_frames),
                '--width', str(self.TARGET_WIDTH),
                '--height', str(self.TARGET_HEIGHT)
            ]
            
            diagnostics["commands_run"].append(" ".join(cmd))
            
            logger.info(f"Starting Remotion render: {output_filename}")
            logger.debug(f"Command: {' '.join(cmd)}")
            
            # Execute render
            result = subprocess.run(
                cmd,
                cwd=str(self.remotion_dir),
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout for rendering
            )
            
            if result.returncode != 0:
                error_msg = f"Remotion render failed: {result.stderr}"
                logger.error(error_msg)
                return RemotionRenderResult(
                    success=False,
                    output_path=None,
                    error_message=error_msg,
                    duration=0,
                    diagnostics=diagnostics
                )
            
            # Step 5: Move output to final location if different
            if str(remotion_output) != output_path:
                shutil.move(str(remotion_output), output_path)
            
            # Step 6: Validate output contract (Finding 2 Fix)
            logger.info(f"Validating Remotion output contract: {output_path}")
            is_valid, validation_diagnostics = self.validate_output_contract(output_path, target_duration)
            diagnostics["validation"] = validation_diagnostics
            
            if not is_valid:
                logger.error(f"Remotion output validation failed: {validation_diagnostics['errors']}")
                diagnostics["validation_warnings"] = validation_diagnostics['errors']
            else:
                logger.info("Remotion output validation passed")
            
            # Step 7: Get final duration
            final_duration = self._get_video_duration(output_path)
            
            logger.info(f"Remotion render complete: {output_path} ({final_duration:.2f}s)")
            
            return RemotionRenderResult(
                success=True,
                output_path=output_path,
                error_message=None if is_valid else f"Validation warnings: {validation_diagnostics['errors']}",
                duration=final_duration,
                diagnostics={
                    **diagnostics,
                    "final_duration": final_duration,
                    "target_duration": target_duration,
                    "duration_delta": abs(final_duration - target_duration)
                }
            )
            
        except subprocess.TimeoutExpired:
            error_msg = "Remotion render timed out after 10 minutes"
            logger.error(error_msg)
            return RemotionRenderResult(
                success=False,
                output_path=None,
                error_message=error_msg,
                duration=0,
                diagnostics=diagnostics
            )
            
        except Exception as e:
            error_msg = f"Remotion render error: {str(e)}"
            logger.exception("Remotion render failed")
            return RemotionRenderResult(
                success=False,
                output_path=None,
                error_message=error_msg,
                duration=0,
                diagnostics=diagnostics
            )
            
        finally:
            # Cleanup temp files
            if temp_input_file and os.path.exists(temp_input_file.name):
                try:
                    os.unlink(temp_input_file.name)
                except:
                    pass
    
    def _transform_edit_plan_for_remotion(self, edit_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform edit plan for Remotion consumption.
        
        Remotion expects paths relative to public/ directory.
        FIXED: Uses source_path from top level (not source_metadata.path)
        """
        # Deep copy to avoid modifying original
        import copy
        remotion_plan = copy.deepcopy(edit_plan)
        
        # FIXED: Transform source_path (top-level) to be relative to public/
        for idx, segment in enumerate(remotion_plan.get("segments", [])):
            # Use source_path from top level (real edit plan structure)
            original_path = segment.get("source_path", "")
            
            if original_path and original_path.startswith("/"):
                # Create a symlink-friendly name
                basename = os.path.basename(original_path)
                segment_id = f"segment_{idx}_{basename}"
                # Keep source_path but store the mapping for _prepare_static_assets
                segment["_remotion_segment_id"] = segment_id
        
        return { "editPlan": remotion_plan }
    
    def _prepare_static_assets(self, edit_plan: Dict[str, Any], public_dir: Path):
        """
        Prepare static assets for Remotion public/ directory.
        Creates symlinks to avoid copying large video files.
        FIXED: Uses source_path from top level (real edit plan structure)
        """
        for idx, segment in enumerate(edit_plan.get("segments", [])):
            # FIXED: Use source_path from top level
            original_path = segment.get("source_path", "")
            
            if not original_path or not os.path.exists(original_path):
                logger.warning(f"Asset not found: {original_path}")
                continue
            
            # Create symlink-friendly name using the segment index
            basename = os.path.basename(original_path)
            segment_id = f"segment_{idx}_{basename}"
            link_path = public_dir / segment_id
            
            # Create symlink (or copy if symlinking fails)
            if not link_path.exists():
                try:
                    os.symlink(original_path, link_path)
                    logger.debug(f"Created symlink: {link_path} -> {original_path}")
                except OSError:
                    # Fallback: copy file
                    shutil.copy2(original_path, link_path)
                    logger.debug(f"Copied asset: {link_path}")
    
    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration using ffprobe"""
        try:
            result = subprocess.run(
                [
                    'ffprobe', '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    video_path
                ],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return float(result.stdout.strip())
        except:
            pass
        return 0.0
    
    # Finding 2 Fix: Add output validation matching FFmpeg renderer contract
    def validate_output_contract(self, output_path: str, target_duration: float = 30.0) -> tuple[bool, Dict[str, Any]]:
        """
        Validate final output meets Instagram contract using ffprobe.
        Matches FFmpegRenderer.validate_output_contract() exactly.
        
        Returns: (is_valid, diagnostics_dict)
        """
        import json
        
        diagnostics = {
            "file": output_path,
            "valid": False,
            "errors": [],
            "streams": {},
            "renderer": "remotion"
        }
        
        if not Path(output_path).exists():
            diagnostics["errors"].append("File does not exist")
            return False, diagnostics
        
        # Run ffprobe (same command as FFmpeg renderer)
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
        
        # Validate video stream (same checks as FFmpeg renderer)
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
            
            if video_stream.get("pix_fmt") != "yuv420p":
                diagnostics["errors"].append(
                    f"Pixel format is {video_stream.get('pix_fmt')}, expected yuv420p"
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
        
        # Validate duration (with 2s tolerance like target_duration contract)
        duration_str = format_info.get("duration")
        if duration_str:
            try:
                duration = float(duration_str)
                diagnostics["duration_seconds"] = duration
                diagnostics["duration_delta"] = abs(duration - target_duration)
                
                # Instagram bounds check (30-60s)
                if duration < 30.0:
                    diagnostics["errors"].append(f"Duration is {duration:.2f}s, minimum is 30s")
                elif duration > 60.0:
                    diagnostics["errors"].append(f"Duration is {duration:.2f}s, maximum is 60s")
                
                # Target tolerance check (2s like edit plan contract)
                if abs(duration - target_duration) > 2.0:
                    diagnostics["errors"].append(
                        f"Duration {duration:.2f}s deviates from target {target_duration}s by >2s"
                    )
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
    
    def get_studio_command(self) -> List[str]:
        """
        Get command to launch Remotion Studio for preview/debugging.
        """
        return ['npx', 'remotion', 'studio']


# Convenience function for API layer
def render_with_remotion(edit_plan: Dict[str, Any], output_path: str) -> RemotionRenderResult:
    """
    Public API for Remotion rendering.
    Feature flag checked at higher level.
    """
    renderer = RemotionRenderer()
    return renderer.render_reel(edit_plan, output_path)
