"""
Reels Maker - Separate module for Instagram Reel creation
Isolated from the existing upload/recommendation flow
"""
import os
import sys
import json
import uuid
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infra.config.database import execute_query, execute_insert, DatabaseError, get_setting
from infra.config.settings import config
from infra.config.logging_config import logger

# Try to import PIL for image preview generation
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL not available, image previews will use source files")

# Import shared reel templates (avoids circular imports)
from shared.reel_templates import REEL_TEMPLATES, PROJECT_STATUSES, RENDER_STATUSES, PUBLISH_STATUSES

# Phase 5: Metrics tracking for observability
# Use a class-based singleton pattern to avoid mutable global state issues
class ReelsMetricsManager:
    """Thread-safe metrics manager for reels operations"""
    
    def __init__(self):
        self._metrics = {
            "total_projects": 0,
            "total_renders": 0,
            "total_publishes": 0,
            "renders_by_status": {
                "completed": 0,
                "failed": 0,
            },
            "publishes_by_status": {
                "published": 0,
                "failed": 0,
            },
            "total_render_duration_ms": 0,
            "total_publish_duration_ms": 0,
            "template_usage": {},
            "last_updated": None,
        }
    
    def update(self, metric_type: str, status: str = None, duration_ms: float = None, template_key: str = None) -> None:
        """Update reels metrics for observability"""
        from datetime import timezone
        self._metrics["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        if metric_type == "project_created":
            self._metrics["total_projects"] += 1
        elif metric_type == "render":
            self._metrics["total_renders"] += 1
            if status in self._metrics["renders_by_status"]:
                self._metrics["renders_by_status"][status] += 1
            if duration_ms:
                self._metrics["total_render_duration_ms"] += duration_ms
        elif metric_type == "publish":
            self._metrics["total_publishes"] += 1
            if status in self._metrics["publishes_by_status"]:
                self._metrics["publishes_by_status"][status] += 1
            if duration_ms:
                self._metrics["total_publish_duration_ms"] += duration_ms
        elif metric_type == "template_used" and template_key:
            self._metrics["template_usage"][template_key] = self._metrics["template_usage"].get(template_key, 0) + 1
    
    def get(self) -> Dict[str, Any]:
        """Get current reels metrics for health/debug visibility (returns a copy)"""
        metrics = dict(self._metrics)
        
        # Calculate averages
        if metrics["total_renders"] > 0:
            completed = metrics["renders_by_status"].get("completed", 0)
            metrics["avg_render_duration_ms"] = (
                metrics["total_render_duration_ms"] / completed if completed > 0 else 0
            )
            metrics["render_success_rate"] = (
                completed / metrics["total_renders"] * 100
            )
        
        if metrics["total_publishes"] > 0:
            published = metrics["publishes_by_status"].get("published", 0)
            metrics["avg_publish_duration_ms"] = (
                metrics["total_publish_duration_ms"] / published if published > 0 else 0
            )
            metrics["publish_success_rate"] = (
                published / metrics["total_publishes"] * 100
            )
        
        return metrics

# Global singleton instance - thread-safe for async operations
_reels_metrics_manager = ReelsMetricsManager()

# Backward-compatible functions
def update_reels_metrics(metric_type: str, status: str = None, duration_ms: float = None, template_key: str = None) -> None:
    """Update reels metrics for observability"""
    _reels_metrics_manager.update(metric_type, status, duration_ms, template_key)

def get_reels_metrics() -> Dict[str, Any]:
    """Get current reels metrics for health/debug visibility"""
    return _reels_metrics_manager.get()

# Pydantic models
class CreateProjectRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    template_key: str = Field(default="dish_showcase")
    transition_style: str = Field(default="auto")  # auto, cut, smooth, fade
    visual_filter: str = Field(default="none")  # none, natural, warm, rich, fresh

class CreateProjectResponse(BaseModel):
    project_id: str
    status: str
    title: str

class ProjectDetail(BaseModel):
    id: str
    title: str
    status: str
    template_key: str
    transition_style: str
    visual_filter: str
    target_duration_seconds: int
    caption: Optional[str]
    hashtags: Optional[List[str]]
    final_output_path: Optional[str]
    final_output_url: Optional[str]
    created_at: str
    updated_at: str

class AssetInfo(BaseModel):
    id: str
    project_id: str
    source_path: str
    preview_url: Optional[str]
    media_type: str
    sort_order: int
    analysis_json: Optional[Dict]
    selected: bool
    created_at: str

class RenderJobInfo(BaseModel):
    id: str
    project_id: str
    status: str
    error_message: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: str

class GenerateRequest(BaseModel):
    target_duration_seconds: int = Field(default=30, ge=30, le=60)
    template_key: Optional[str] = None

class ProjectFullResponse(BaseModel):
    project: ProjectDetail
    assets: List[AssetInfo]
    latest_render: Optional[RenderJobInfo]

# Storage utilities
def get_reels_base_dir() -> Path:
    """Get base directory for reel projects storage"""
    reels_dir = Path(config.UPLOADS_DIR) / "reels"
    reels_dir.mkdir(parents=True, exist_ok=True)
    return reels_dir

def get_project_dirs(project_id: str) -> Dict[str, Path]:
    """Get project-scoped directory paths"""
    base = get_reels_base_dir() / project_id
    return {
        "base": base,
        "source": base / "source",
        "output": base / "output",
        "previews": base / "previews"
    }

def ensure_project_dirs(project_id: str):
    """Create all project directories if they don't exist"""
    dirs = get_project_dirs(project_id)
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs

def cleanup_project_storage(project_id: str):
    """Remove all project files and directories"""
    try:
        base_dir = get_reels_base_dir() / project_id
        if base_dir.exists():
            shutil.rmtree(base_dir)
            logger.info(f"Cleaned up storage for project {project_id}")
    except Exception as e:
        logger.error(f"Failed to cleanup project storage {project_id}: {e}")

# Preview generation utilities
def generate_asset_preview(source_path: str, media_type: str, previews_dir: Path) -> Optional[str]:
    """
    Generate a browser-safe preview image for an asset.
    For images: create a JPEG thumbnail
    For videos: extract a poster frame using ffmpeg
    Returns the preview file path or None if generation fails.
    """
    try:
        source = Path(source_path)
        preview_filename = f"{source.stem}_preview.jpg"
        preview_path = previews_dir / preview_filename
        
        if media_type == "image":
            # Handle HEIC/HEIF files - convert to JPEG first if needed
            ext = source.suffix.lower()
            if ext in ['.heic', '.heif']:
                try:
                    # Try to use heif-convert or similar if available
                    import subprocess
                    temp_jpeg = previews_dir / f"{source.stem}_temp.jpg"
                    result = subprocess.run(
                        ['heif-convert', str(source), str(temp_jpeg)],
                        capture_output=True,
                        timeout=10
                    )
                    if result.returncode == 0 and temp_jpeg.exists():
                        # Now generate thumbnail from converted JPEG
                        if PIL_AVAILABLE:
                            with Image.open(temp_jpeg) as img:
                                img.thumbnail((400, 400), Image.Resampling.LANCZOS)
                                img = img.convert('RGB')
                                img.save(preview_path, 'JPEG', quality=85)
                        temp_jpeg.unlink(missing_ok=True)
                    else:
                        # Fallback - use source path for HEIC without preview
                        logger.warning(f"HEIC conversion failed for {source}, using source")
                        return None
                except Exception as e:
                    logger.warning(f"HEIC conversion error: {e}, using source")
                    return None
            elif PIL_AVAILABLE:
                # Use PIL to create thumbnail
                with Image.open(source) as img:
                    img.thumbnail((400, 400), Image.Resampling.LANCZOS)
                    # Convert to RGB for consistent output
                    if img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')
                    img.save(preview_path, 'JPEG', quality=85)
            else:
                # No PIL available - return None to use source
                return None
        
        elif media_type == "video":
            # Use ffmpeg to extract first frame
            try:
                result = subprocess.run(
                    [
                        'ffmpeg', '-y', '-i', str(source),
                        '-ss', '00:00:00.500',  # Extract at 0.5 seconds
                        '-vframes', '1',
                        '-q:v', '2',  # High quality
                        str(preview_path)
                    ],
                    capture_output=True,
                    timeout=30
                )
                if result.returncode != 0:
                    logger.warning(f"ffmpeg failed for video preview: {result.stderr.decode()[:200]}")
                    return None
            except subprocess.TimeoutExpired:
                logger.warning(f"ffmpeg timeout for video preview: {source}")
                return None
            except FileNotFoundError:
                logger.warning("ffmpeg not available for video previews")
                return None
        
        if preview_path.exists():
            return str(preview_path)
        return None
        
    except Exception as e:
        logger.error(f"Failed to generate preview for {source_path}: {e}")
        return None

def get_preview_url(preview_path: Optional[str]) -> Optional[str]:
    """Convert a preview file path to a web-accessible URL"""
    if not preview_path:
        return None
    try:
        preview = Path(preview_path)
        if preview.exists():
            relative = preview.relative_to(Path(config.UPLOADS_DIR))
            return f"/uploads/{relative}"
    except Exception as e:
        logger.warning(f"Failed to get preview URL for {preview_path}: {e}")
    return None

# Database operations
def create_project_db(title: str, template_key: str, transition_style: str = "auto", visual_filter: str = "none") -> str:
    """Create a new reel project in database"""
    project_id = str(uuid.uuid4())
    
    if template_key not in REEL_TEMPLATES:
        template_key = "dish_showcase"
    
    # Validate and default style settings
    valid_transitions = ["auto", "cut", "smooth", "fade"]
    if transition_style not in valid_transitions:
        transition_style = "auto"
    
    valid_filters = ["none", "natural", "warm", "rich", "fresh"]
    if visual_filter not in valid_filters:
        visual_filter = "none"
    
    try:
        execute_insert(
            """
            INSERT INTO reel_projects (id, title, status, template_key, transition_style, visual_filter, target_duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, title, "draft", template_key, transition_style, visual_filter, 30)
        )
        
        # Create storage directories
        ensure_project_dirs(project_id)
        
        logger.info(f"Created reel project {project_id}: {title} (transition={transition_style}, filter={visual_filter})")
        return project_id
    except DatabaseError as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=500, detail="Failed to create project")

def get_project_db(project_id: str) -> Optional[Dict]:
    """Get project details from database"""
    try:
        rows = execute_query(
            "SELECT * FROM reel_projects WHERE id = ?",
            (project_id,)
        )
        if rows:
            row = dict(rows[0])  # Convert sqlite3.Row to dict
            return {
                "id": row["id"],
                "title": row["title"],
                "status": row["status"],
                "template_key": row["template_key"],
                "transition_style": row.get("transition_style", "auto"),
                "visual_filter": row.get("visual_filter", "none"),
                "target_duration_seconds": row["target_duration_seconds"],
                "caption": row["caption"],
                "hashtags": json.loads(row["hashtags"]) if row["hashtags"] else None,
                "final_output_path": row["final_output_path"],
                "final_output_url": row["final_output_url"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
        return None
    except DatabaseError as e:
        logger.error(f"Failed to get project {project_id}: {e}")
        return None

def get_project_assets_db(project_id: str) -> List[Dict]:
    """Get all assets for a project"""
    try:
        rows = execute_query(
            "SELECT * FROM reel_assets WHERE project_id = ? ORDER BY sort_order, created_at",
            (project_id,)
        )
        assets = []
        for row in rows:
            asset = {
                "id": row["id"],
                "project_id": row["project_id"],
                "source_path": row["source_path"],
                "media_type": row["media_type"],
                "sort_order": row["sort_order"],
                "analysis_json": json.loads(row["analysis_json"]) if row["analysis_json"] else None,
                "selected": bool(row["selected"]),
                "preview_path": row["preview_path"],
                "created_at": row["created_at"]
            }
            # Generate preview URL using utility function
            asset["preview_url"] = get_preview_url(asset["preview_path"])
            assets.append(asset)
        return assets
    except DatabaseError as e:
        logger.error(f"Failed to get assets for project {project_id}: {e}")
        return []

def get_latest_render_job_db(project_id: str) -> Optional[Dict]:
    """Get the most recent render job for a project"""
    try:
        rows = execute_query(
            "SELECT * FROM reel_render_jobs WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (project_id,)
        )
        if rows:
            row = rows[0]
            return {
                "id": row["id"],
                "project_id": row["project_id"],
                "status": row["status"],
                "error_message": row["error_message"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "created_at": row["created_at"]
            }
        return None
    except DatabaseError as e:
        logger.error(f"Failed to get render job for project {project_id}: {e}")
        return None

def get_render_job_by_id_db(job_id: str) -> Optional[Dict]:
    """Get a specific render job by its ID"""
    try:
        rows = execute_query(
            "SELECT * FROM reel_render_jobs WHERE id = ?",
            (job_id,)
        )
        if rows:
            row = rows[0]
            return {
                "id": row["id"],
                "project_id": row["project_id"],
                "status": row["status"],
                "error_message": row["error_message"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "created_at": row["created_at"]
            }
        return None
    except DatabaseError as e:
        logger.error(f"Failed to get render job {job_id}: {e}")
        return None

def add_asset_db(project_id: str, source_path: str, media_type: str, sort_order: int, preview_path: Optional[str] = None) -> str:
    """Add an asset to a project"""
    asset_id = str(uuid.uuid4())
    try:
        execute_insert(
            "INSERT INTO reel_assets (id, project_id, source_path, media_type, sort_order, preview_path) VALUES (?, ?, ?, ?, ?, ?)",
            (asset_id, project_id, source_path, media_type, sort_order, preview_path)
        )
        return asset_id
    except DatabaseError as e:
        logger.error(f"Failed to add asset: {e}")
        raise HTTPException(status_code=500, detail="Failed to add asset")

def update_asset_preview_db(asset_id: str, preview_path: str):
    """Update an asset with its preview path"""
    try:
        execute_insert(
            "UPDATE reel_assets SET preview_path = ? WHERE id = ?",
            (preview_path, asset_id)
        )
    except DatabaseError as e:
        logger.error(f"Failed to update asset preview: {e}")

def create_render_job_db(project_id: str) -> str:
    """Create a new render job"""
    job_id = str(uuid.uuid4())
    try:
        execute_insert(
            "INSERT INTO reel_render_jobs (id, project_id, status) VALUES (?, ?, ?)",
            (job_id, project_id, "queued")
        )
        # Update project status
        execute_insert(
            "UPDATE reel_projects SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            ("queued", project_id)
        )
        return job_id
    except DatabaseError as e:
        logger.error(f"Failed to create render job: {e}")
        raise HTTPException(status_code=500, detail="Failed to create render job")

def delete_asset_db(asset_id: str) -> bool:
    """Delete a single asset and its files from disk"""
    try:
        rows = execute_query("SELECT source_path, preview_path FROM reel_assets WHERE id = ?", (asset_id,))
        if not rows:
            return False
        row = rows[0]
        for path_field in (row["source_path"], row["preview_path"]):
            if path_field:
                p = Path(path_field)
                if p.exists():
                    p.unlink()
        execute_insert("DELETE FROM reel_assets WHERE id = ?", (asset_id,))
        logger.info(f"Deleted asset {asset_id}")
        return True
    except DatabaseError as e:
        logger.error(f"Failed to delete asset {asset_id}: {e}")
        return False

def delete_project_db(project_id: str) -> bool:
    """Delete a project and all associated data"""
    try:
        # Database cascade will handle related records
        execute_insert("DELETE FROM reel_projects WHERE id = ?", (project_id,))
        # Clean up storage
        cleanup_project_storage(project_id)
        return True
    except DatabaseError as e:
        logger.error(f"Failed to delete project {project_id}: {e}")
        return False

def list_projects_db(limit: int = 50) -> List[Dict]:
    """List all projects ordered by creation date"""
    try:
        rows = execute_query(
            "SELECT * FROM reel_projects ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        projects = []
        for row in rows:
            projects.append({
                "id": row["id"],
                "title": row["title"],
                "status": row["status"],
                "template_key": row["template_key"],
                "created_at": row["created_at"]
            })
        return projects
    except DatabaseError as e:
        logger.error(f"Failed to list projects: {e}")
        return []

# API Router
router = APIRouter(prefix="/api/reels", tags=["reels"])

@router.post("/projects", response_model=CreateProjectResponse)
async def create_project(request: CreateProjectRequest):
    """Create a new Reel Maker project"""
    if request.template_key not in REEL_TEMPLATES:
        raise HTTPException(status_code=400, detail=f"Invalid template_key. Valid: {list(REEL_TEMPLATES.keys())}")
    
    project_id = create_project_db(
        request.title, 
        request.template_key,
        request.transition_style,
        request.visual_filter
    )
    
    # Phase 5: Track metrics
    update_reels_metrics("project_created")
    update_reels_metrics("template_used", template_key=request.template_key)
    
    return CreateProjectResponse(
        project_id=project_id,
        status="draft",
        title=request.title
    )

def get_next_sort_order(project_id: str) -> int:
    """Get the next sort_order for a project (append after existing assets)"""
    try:
        rows = execute_query(
            "SELECT MAX(sort_order) as max_order FROM reel_assets WHERE project_id = ?",
            (project_id,)
        )
        if rows and rows[0]["max_order"] is not None:
            return rows[0]["max_order"] + 1
        return 0
    except DatabaseError:
        return 0

@router.post("/projects/{project_id}/assets")
async def upload_assets(project_id: str, files: List[UploadFile] = File(...)):
    """Upload multiple images/videos to a Reel project"""
    # Verify project exists
    project = get_project_db(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project["status"] not in ["draft", "ready", "failed"]:
        raise HTTPException(status_code=400, detail=f"Cannot upload to project with status: {project['status']}")
    
    dirs = get_project_dirs(project_id)
    uploaded_assets = []
    
    # Get starting sort_order for this batch (append after existing)
    next_sort_order = get_next_sort_order(project_id)
    
    for idx, file in enumerate(files):
        # Validate file type
        ext = Path(file.filename).suffix.lower()
        valid_image = ext in ['.jpg', '.jpeg', '.png', '.heic', '.heif', '.webp']
        valid_video = ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']
        
        if not (valid_image or valid_video):
            logger.warning(f"Skipping unsupported file: {file.filename}")
            continue
        
        media_type = "video" if valid_video else "image"
        
        # Save source file
        safe_name = f"{uuid.uuid4().hex}{ext}"
        source_path = dirs["source"] / safe_name
        
        try:
            with open(source_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            
            # Generate browser-safe preview
            preview_path = generate_asset_preview(str(source_path), media_type, dirs["previews"])
            
            # Add to database with sequential sort_order (append after existing assets)
            sort_order = next_sort_order + idx
            asset_id = add_asset_db(project_id, str(source_path), media_type, sort_order, preview_path)
            
            # Get preview URL for response
            preview_url = get_preview_url(preview_path)
            
            uploaded_assets.append({
                "asset_id": asset_id,
                "filename": file.filename,
                "media_type": media_type,
                "source_path": str(source_path),
                "preview_path": preview_path,
                "preview_url": preview_url
            })
            
            logger.info(f"Uploaded {media_type} asset {asset_id} for project {project_id} (preview: {preview_path is not None})")
        except Exception as e:
            logger.error(f"Failed to upload {file.filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to upload {file.filename}")
    
    return {
        "project_id": project_id,
        "assets_uploaded": len(uploaded_assets),
        "assets": uploaded_assets
    }

@router.delete("/projects/{project_id}/assets/{asset_id}")
async def delete_asset(project_id: str, asset_id: str):
    """Remove a single asset from a project"""
    project = get_project_db(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["status"] in ["queued", "analyzing", "rendering"]:
        raise HTTPException(status_code=400, detail="Cannot remove assets while project is processing")
    rows = execute_query("SELECT id FROM reel_assets WHERE id = ? AND project_id = ?", (asset_id, project_id))
    if not rows:
        raise HTTPException(status_code=404, detail="Asset not found")
    if delete_asset_db(asset_id):
        return {"status": "deleted", "asset_id": asset_id}
    raise HTTPException(status_code=500, detail="Failed to delete asset")

@router.get("/projects/{project_id}", response_model=ProjectFullResponse)
async def get_project(project_id: str):
    """Fetch project details, assets, and latest render"""
    project = get_project_db(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    assets = get_project_assets_db(project_id)
    latest_render = get_latest_render_job_db(project_id)

    return ProjectFullResponse(
        project=ProjectDetail(**project),
        assets=[AssetInfo(**a) for a in assets],
        latest_render=RenderJobInfo(**latest_render) if latest_render else None
    )


# Import recommendation functions
LLM_AVAILABLE = False
try:
    from infra.integrations.llm_client import generate_reel_recommendation, LLMError
    LLM_AVAILABLE = True
except ImportError:
    logger.warning("LLM client not available for reel recommendations")


class ReelRecommendationResponse(BaseModel):
    content_analysis: Dict[str, Any]
    caption_variants: List[Dict[str, str]]
    hashtag_variants: List[Dict[str, Any]]
    optimal_time: Dict[str, str]
    reel_specific: Dict[str, str]
    strategy_notes: str
    confidence_score: float
    content_patterns: List[str]
    recommendation_id: str


class RecommendationRequest(BaseModel):
    context: Optional[str] = None

@router.post("/projects/{project_id}/recommendations", response_model=ReelRecommendationResponse)
async def get_reel_recommendations(project_id: str, request: RecommendationRequest = None):
    """
    Generate AI recommendations for a reel project.
    Analyzes the first selected video asset and returns caption variants,
    hashtag variants, optimal posting time, and reel-specific guidance.
    """
    # Get project
    project = get_project_db(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get assets - prefer selected assets, fallback to first video
    assets = get_project_assets_db(project_id)
    if not assets:
        raise HTTPException(status_code=400, detail="No assets found for this project")

    # Find a suitable video asset
    video_asset = None
    for asset in assets:
        if asset.get("selected") and asset.get("media_type") == "video":
            video_asset = asset
            break
    if not video_asset:
        for asset in assets:
            if asset.get("media_type") == "video":
                video_asset = asset
                break

    if not video_asset:
        raise HTTPException(status_code=400, detail="No video assets found for recommendation")

    # Check if we have cached recommendations
    cached = get_cached_recommendation(project_id)
    if cached:
        return ReelRecommendationResponse(**cached)

    # Generate recommendation
    if not LLM_AVAILABLE:
        raise HTTPException(status_code=503, detail="Recommendation service unavailable")

    try:
        filepath = video_asset["source_path"]
        # Use user-provided context if available, otherwise fall back to project title
        user_context = request.context if request and request.context else ""
        context = user_context or project.get("title", "")

        # Get visual analysis if available
        visual_analysis = None
        if video_asset.get("analysis_json"):
            analysis = video_asset["analysis_json"]
            # Handle both dict (already parsed) and string (needs parsing)
            if isinstance(analysis, str):
                analysis = json.loads(analysis)
            visual_analysis = analysis.get("visual_facts", {}) if isinstance(analysis, dict) else {}

        # Call LLM for recommendation
        recommendation = generate_reel_recommendation(
            filepath=filepath,
            context=context,
            visual_analysis=visual_analysis,
            _allow_internal_visual=False  # Skip visual analysis to keep it fast
        )

        # Add metadata
        recommendation["recommendation_id"] = str(uuid.uuid4())

        # Cache the recommendation
        cache_recommendation(project_id, recommendation)

        return ReelRecommendationResponse(**recommendation)

    except LLMError as e:
        logger.error(f"LLM recommendation failed for project {project_id}: {e}")
        raise HTTPException(status_code=503, detail=f"Recommendation generation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error generating recommendations: {e}")
        raise HTTPException(status_code=500, detail="Internal error generating recommendations")


def get_cached_recommendation(project_id: str) -> Optional[Dict]:
    """Get cached recommendation if recent (< 1 hour)"""
    try:
        result = execute_query(
            "SELECT recommendation_json, created_at FROM reel_recommendations WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (project_id,)
        )
        if result:
            row = result[0]
            created = datetime.fromisoformat(row["created_at"])
            if (datetime.now() - created).seconds < 3600:  # 1 hour cache
                return json.loads(row["recommendation_json"])
    except Exception as e:
        logger.warning(f"Failed to get cached recommendation: {e}")
    return None


def cache_recommendation(project_id: str, recommendation: Dict):
    """Cache recommendation to database"""
    try:
        rec_id = recommendation.get("recommendation_id", str(uuid.uuid4()))
        execute_insert(
            """INSERT INTO reel_recommendations (id, project_id, recommendation_json, created_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
            (rec_id, project_id, json.dumps(recommendation))
        )
    except Exception as e:
        logger.warning(f"Failed to cache recommendation: {e}")


class UpdateProjectRequest(BaseModel):
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    transition_style: Optional[str] = None  # auto, cut, smooth, fade
    visual_filter: Optional[str] = None  # none, natural, warm, rich, fresh


class UpdateStyleRequest(BaseModel):
    transition_style: Optional[str] = Field(None, description="Transition style: auto, cut, smooth, fade")
    visual_filter: Optional[str] = Field(None, description="Visual filter: none, natural, warm, rich, fresh")


@router.post("/projects/{project_id}/update")
async def update_project(project_id: str, request: UpdateProjectRequest):
    """Update project metadata (caption, hashtags, style settings)"""
    project = get_project_db(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        hashtags_str = json.dumps(request.hashtags) if request.hashtags else None
        
        # Build update fields dynamically
        update_fields = ["caption = ?", "hashtags = ?"]
        params = [request.caption, hashtags_str]
        
        if request.transition_style is not None:
            update_fields.append("transition_style = ?")
            params.append(request.transition_style)
        
        if request.visual_filter is not None:
            update_fields.append("visual_filter = ?")
            params.append(request.visual_filter)
        
        params.append(project_id)
        
        query = f"UPDATE reel_projects SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        execute_insert(query, tuple(params))
        
        return {"status": "updated", "project_id": project_id}
    except DatabaseError as e:
        logger.error(f"Failed to update project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update project")


@router.post("/projects/{project_id}/style")
async def update_project_style(project_id: str, request: UpdateStyleRequest):
    """
    Update project style settings (transition and filter).
    These settings persist for generate and regenerate operations.
    Accepts partial updates - only provided fields are updated.
    """
    project = get_project_db(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Track which fields to update
    update_fields = []
    params = []
    result = {"status": "updated", "project_id": project_id}
    
    # Validate and update transition_style if provided
    if request.transition_style is not None:
        valid_transitions = ["auto", "cut", "smooth", "fade"]
        if request.transition_style not in valid_transitions:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid transition_style. Must be one of: {', '.join(valid_transitions)}"
            )
        update_fields.append("transition_style = ?")
        params.append(request.transition_style)
        result["transition_style"] = request.transition_style
    
    # Validate and update visual_filter if provided
    if request.visual_filter is not None:
        valid_filters = ["none", "natural", "warm", "rich", "fresh"]
        if request.visual_filter not in valid_filters:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid visual_filter. Must be one of: {', '.join(valid_filters)}"
            )
        update_fields.append("visual_filter = ?")
        params.append(request.visual_filter)
        result["visual_filter"] = request.visual_filter
    
    # If no fields to update, return early
    if not update_fields:
        return result
    
    try:
        query = f"UPDATE reel_projects SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        params.append(project_id)
        execute_insert(query, tuple(params))
        
        logger.info(f"Updated style settings for project {project_id}: {result}")
        
        return result
    except DatabaseError as e:
        logger.error(f"Failed to update style settings for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update style settings")


class ScheduleReelRequest(BaseModel):
    caption: str
    hashtags: List[str]
    scheduled_time: Optional[str] = Field(None, description="ISO timestamp for scheduling")


class ScheduleReelResponse(BaseModel):
    status: str
    schedule_id: str
    project_id: str
    scheduled_time: str


@router.post("/projects/{project_id}/schedule", response_model=ScheduleReelResponse)
async def schedule_reel(project_id: str, request: ScheduleReelRequest):
    """
    Schedule a reel for future publishing.
    Stores caption, hashtags, and scheduled time for later publishing.
    """
    # Verify project exists and is ready
    project = get_project_db(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project["status"] not in ["ready", "published"]:
        raise HTTPException(status_code=400, detail="Reel must be rendered before scheduling")

    # Use provided time or default to tomorrow at optimal time (6 PM)
    scheduled_time = request.scheduled_time
    if not scheduled_time:
        scheduled_time = (datetime.now() + timedelta(days=1)).replace(
            hour=18, minute=0, second=0, microsecond=0
        ).isoformat()

    # Validate time is in the future
    try:
        schedule_dt = datetime.fromisoformat(scheduled_time)
        if schedule_dt < datetime.now():
            raise HTTPException(status_code=400, detail="Scheduled time must be in the future")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid scheduled_time format")

    # Create schedule entry
    schedule_id = str(uuid.uuid4())
    hashtags_str = json.dumps(request.hashtags)

    try:
        execute_insert(
            """INSERT INTO scheduled_reel_posts (id, project_id, caption, hashtags, scheduled_time, status)
               VALUES (?, ?, ?, ?, ?, 'pending')""",
            (schedule_id, project_id, request.caption, hashtags_str, scheduled_time)
        )

        # Also update the project with the caption/hashtags for reference
        execute_insert(
            "UPDATE reel_projects SET caption = ?, hashtags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (request.caption, hashtags_str, project_id)
        )

        logger.info(f"Reel scheduled: {schedule_id} for project {project_id} at {scheduled_time}")

        return ScheduleReelResponse(
            status="scheduled",
            schedule_id=schedule_id,
            project_id=project_id,
            scheduled_time=scheduled_time
        )

    except DatabaseError as e:
        logger.error(f"Failed to schedule reel {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to schedule reel")


@router.get("/projects/{project_id}/schedule")
async def get_reel_schedule(project_id: str):
    """Get scheduled posts for a reel project"""
    try:
        result = execute_query(
            """SELECT id, scheduled_time, status FROM scheduled_reel_posts
               WHERE project_id = ? AND status = 'pending'
               ORDER BY scheduled_time""",
            (project_id,)
        )
        return {
            "project_id": project_id,
            "scheduled_posts": [
                {"schedule_id": r["id"], "scheduled_time": r["scheduled_time"], "status": r["status"]}
                for r in result
            ]
        }
    except DatabaseError:
        return {"project_id": project_id, "scheduled_posts": []}


def update_render_job_status(job_id: str, status: str, error_message: Optional[str] = None):
    """Update render job status and timestamps"""
    try:
        if status == "running":
            execute_insert(
                "UPDATE reel_render_jobs SET status = ?, started_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, job_id)
            )
        elif status in ["completed", "failed"]:
            execute_insert(
                "UPDATE reel_render_jobs SET status = ?, error_message = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, error_message, job_id)
            )
        else:
            execute_insert(
                "UPDATE reel_render_jobs SET status = ? WHERE id = ?",
                (status, job_id)
            )
    except DatabaseError as e:
        logger.error(f"Failed to update job {job_id} status: {e}")

def update_project_status(project_id: str, status: str):
    """Update project status and timestamp"""
    try:
        execute_insert(
            "UPDATE reel_projects SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, project_id)
        )
    except DatabaseError as e:
        logger.error(f"Failed to update project {project_id} status: {e}")

# Import Phase 2 analyzer
try:
    from workers.reels.analyzer import (
        analyze_reel_asset,
        select_assets_for_reel,
        generate_edit_plan,
        validate_edit_plan,
        update_asset_analysis_db,
        update_job_edit_plan_db
    )
    ANALYZER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Reel analyzer not available: {e}")
    ANALYZER_AVAILABLE = False

# Import Phase 3 renderer
try:
    from workers.reels.renderer import FFmpegRenderer, RenderResult
    RENDERER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Reel renderer not available: {e}")
    RENDERER_AVAILABLE = False

async def process_reel_generation(project_id: str, job_id: str, template_key: str, target_duration: int):
    """
    Background task for Phase 2: Analysis & Planning.
    Analyzes assets, generates edit plan, and renders the reel.
    """
    import time
    render_start_time = time.time()
    
    logger.info(f"Starting reel generation for project {project_id}, job {job_id}")
    
    try:
        # Step 0: Get project details (includes style settings)
        project = get_project_db(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        transition_style = project.get("transition_style", "auto")
        visual_filter = project.get("visual_filter", "none")
        
        logger.info(f"Project {project_id} style settings: transition={transition_style}, filter={visual_filter}")
        
        # Step 1: Update status to analyzing
        update_render_job_status(job_id, "analyzing")
        update_project_status(project_id, "analyzing")
        
        # Get assets
        assets = get_project_assets_db(project_id)
        if not assets:
            raise ValueError("No assets found in project")
        
        # Step 2: Analyze each asset
        logger.info(f"Analyzing {len(assets)} assets for project {project_id}")
        for asset in assets:
            if not asset.get("analysis_json"):
                # Run analysis
                analysis = analyze_reel_asset(
                    asset["id"],
                    asset["source_path"],
                    asset["media_type"]
                )
                # Store results
                update_asset_analysis_db(asset["id"], analysis)
                asset["analysis_json"] = analysis
        
        # Step 3: Select and score assets for reel
        logger.info(f"Selecting assets for reel from project {project_id}")
        selected_assets = select_assets_for_reel(assets, target_duration)
        if not selected_assets:
            raise ValueError("No suitable assets selected for reel")
        
        # Step 4: Generate edit plan with transition style
        logger.info(f"Generating edit plan for project {project_id} with transition={transition_style}")
        edit_plan = generate_edit_plan(project_id, selected_assets, template_key, target_duration, transition_style)
        
        # Step 5: Validate edit plan
        is_valid, error_msg = validate_edit_plan(edit_plan)
        if not is_valid:
            raise ValueError(f"Invalid edit plan: {error_msg}")
        
        # Store edit plan
        update_job_edit_plan_db(job_id, edit_plan)
        
        # Step 6: Mark edit plan as ready (Phase 2 complete)
        update_render_job_status(job_id, "plan_ready")
        update_project_status(project_id, "plan_ready")
        
        logger.info(f"Phase 2 complete for project {project_id} - edit plan ready")
        
        # Step 7: Phase 3 - Render Video
        if not RENDERER_AVAILABLE:
            logger.warning(f"Renderer not available for project {project_id}")
            update_render_job_status(job_id, "failed", "Video renderer not available")
            update_project_status(project_id, "failed")
            return
        
        logger.info(f"Starting Phase 3 render for project {project_id}")
        update_render_job_status(job_id, "running")
        update_project_status(project_id, "rendering")
        
        # Setup output paths
        dirs = get_project_dirs(project_id)
        output_filename = f"reel_{job_id[:8]}.mp4"
        output_path = dirs["output"] / output_filename
        poster_path = dirs["output"] / f"reel_{job_id[:8]}_poster.jpg"
        
        # Render the reel with visual filter
        renderer = FFmpegRenderer(visual_filter=visual_filter)
        render_result = renderer.render_reel(edit_plan, str(output_path))
        
        if not render_result.success:
            logger.error(f"Render failed for project {project_id}: {render_result.error_message}")
            update_render_job_status(job_id, "failed", render_result.error_message)
            update_project_status(project_id, "failed")
            return
        
        # Generate poster frame
        poster_success = renderer.generate_poster_frame(str(output_path), str(poster_path))
        if poster_success:
            logger.info(f"Poster generated for project {project_id}: {poster_path}")
        
        # Update project with output info
        output_url = f"/uploads/reels/{project_id}/output/{output_filename}"
        try:
            execute_insert(
                """
                UPDATE reel_projects 
                SET final_output_path = ?, final_output_url = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (str(output_path), output_url, project_id)
            )
        except DatabaseError as e:
            logger.error(f"Failed to update project output: {e}")
        
        # Validate output contract before marking ready
        validation_passed = True
        if render_result.diagnostics and "validation" in render_result.diagnostics:
            validation = render_result.diagnostics["validation"]
            if not validation.get("valid", False):
                logger.warning(f"Output validation failed for project {project_id}: {validation.get('errors', [])}")
                validation_passed = False
        
        # Phase 5: Track render metrics
        render_duration_ms = (time.time() - render_start_time) * 1000
        
        # Only mark ready if validation passed
        if validation_passed:
            update_render_job_status(job_id, "completed")
            update_project_status(project_id, "ready")
            update_reels_metrics("render", status="completed", duration_ms=render_duration_ms)
        else:
            update_render_job_status(job_id, "failed", f"Output validation failed: {validation.get('errors', [])}")
            update_project_status(project_id, "failed")
            update_reels_metrics("render", status="failed", duration_ms=render_duration_ms)
        
        logger.info(f"Phase 3 complete for project {project_id} - video rendered: {output_path}")
        
    except Exception as e:
        logger.error(f"Reel generation failed for project {project_id}: {e}")
        update_render_job_status(job_id, "failed", str(e))
        update_project_status(project_id, "failed")
        
        # Phase 5: Track render failure
        update_reels_metrics("render", status="failed")

@router.post("/projects/{project_id}/generate")
async def generate_reel(project_id: str, request: GenerateRequest, background_tasks: BackgroundTasks):
    """Analyze assets and enqueue Reel generation"""
    project = get_project_db(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check for assets
    assets = get_project_assets_db(project_id)
    if not assets:
        raise HTTPException(status_code=400, detail="No assets in project. Upload assets first.")
    
    # Validate template if provided
    template = request.template_key or project["template_key"]
    if template not in REEL_TEMPLATES:
        raise HTTPException(status_code=400, detail=f"Invalid template: {template}")
    
    # Check analyzer availability
    if not ANALYZER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Reel analyzer not available. Please check system configuration.")
    
    # Create render job
    job_id = create_render_job_db(project_id)
    
    # Queue background processing (Phase 2: Analysis & Planning)
    background_tasks.add_task(
        process_reel_generation,
        project_id,
        job_id,
        template,
        request.target_duration_seconds
    )
    
    logger.info(f"Queued reel generation job {job_id} for project {project_id}")
    
    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Reel generation started. Analyzing assets and creating edit plan..."
    }

@router.post("/projects/{project_id}/regenerate")
async def regenerate_reel(project_id: str, request: GenerateRequest, background_tasks: BackgroundTasks):
    """
    Regenerate a Reel from existing assets.
    Allows changing template or trying again after failure.
    """
    project = get_project_db(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check for assets
    assets = get_project_assets_db(project_id)
    if not assets:
        raise HTTPException(status_code=400, detail="No assets in project. Upload assets first.")
    
    # Validate template if provided (or use existing)
    template = request.template_key or project["template_key"]
    if template not in REEL_TEMPLATES:
        raise HTTPException(status_code=400, detail=f"Invalid template: {template}")
    
    # Check analyzer availability
    if not ANALYZER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Reel analyzer not available. Please check system configuration.")
    
    # Clear previous output if exists
    if project.get("final_output_path"):
        try:
            output_file = Path(project["final_output_path"])
            if output_file.exists():
                output_file.unlink()
                logger.info(f"Cleared previous output for project {project_id}")
        except Exception as e:
            logger.warning(f"Failed to clear previous output: {e}")
    
    # Create new render job
    job_id = create_render_job_db(project_id)
    
    # Queue background processing
    background_tasks.add_task(
        process_reel_generation,
        project_id,
        job_id,
        template,
        request.target_duration_seconds
    )
    
    logger.info(f"Queued reel regeneration job {job_id} for project {project_id}")
    
    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Reel regeneration started. Re-analyzing assets with new template..."
    }

@router.get("/projects/{project_id}/jobs/{job_id}")
async def get_job_status(project_id: str, job_id: str):
    """Poll render job status - queries specific job_id directly"""
    job = get_render_job_by_id_db(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Verify job belongs to this project
    if job["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="Job not found for this project")
    
    return job

@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete project and all associated assets/outputs"""
    project = get_project_db(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if delete_project_db(project_id):
        return {"status": "deleted", "project_id": project_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete project")

@router.get("/templates")
async def list_templates():
    """List available reel templates"""
    return REEL_TEMPLATES

@router.get("/projects")
async def list_projects(limit: int = 50):
    """List all reel projects"""
    projects = list_projects_db(limit)
    return {"projects": projects, "count": len(projects)}


@router.get("/metrics")
async def get_metrics():
    """
    Get Reels Maker metrics for observability.
    Returns render/publish statistics and health indicators.
    """
    metrics = get_reels_metrics()
    return {
        "reels_metrics": metrics,
        "templates_available": len(REEL_TEMPLATES),
        "template_list": list(REEL_TEMPLATES.keys()),
        "analyzer_available": ANALYZER_AVAILABLE,
        "renderer_available": RENDERER_AVAILABLE,
    }


# Phase 4: Publishing endpoints
class PublishRequest(BaseModel):
    caption: str = Field(default="")
    hashtags: List[str] = Field(default_factory=list)
    share_to_feed: bool = Field(default=True)


class PublishResponse(BaseModel):
    publish_job_id: str
    status: str
    message: str
    instagram_media_id: Optional[str] = None


def create_publish_job_db(project_id: str) -> str:
    """Create a new publish job"""
    job_id = str(uuid.uuid4())
    try:
        execute_insert(
            "INSERT INTO reel_publish_jobs (id, project_id, status) VALUES (?, ?, ?)",
            (job_id, project_id, "queued")
        )
        return job_id
    except DatabaseError as e:
        logger.error(f"Failed to create publish job: {e}")
        raise HTTPException(status_code=500, detail="Failed to create publish job")


def update_publish_job_status(job_id: str, status: str, external_media_id: Optional[str] = None, error_message: Optional[str] = None):
    """Update publish job status"""
    try:
        if status in ["published", "failed"]:
            execute_insert(
                """
                UPDATE reel_publish_jobs 
                SET status = ?, external_media_id = ?, error_message = ?, completed_at = CURRENT_TIMESTAMP 
                WHERE id = ?
                """,
                (status, external_media_id, error_message, job_id)
            )
        else:
            execute_insert(
                "UPDATE reel_publish_jobs SET status = ? WHERE id = ?",
                (status, job_id)
            )
    except DatabaseError as e:
        logger.error(f"Failed to update publish job {job_id}: {e}")


def get_publish_job_db(job_id: str) -> Optional[Dict]:
    """Get publish job by ID"""
    try:
        rows = execute_query(
            "SELECT * FROM reel_publish_jobs WHERE id = ?",
            (job_id,)
        )
        if rows:
            row = rows[0]
            return {
                "id": row["id"],
                "project_id": row["project_id"],
                "status": row["status"],
                "external_media_id": row["external_media_id"],
                "error_message": row["error_message"],
                "created_at": row["created_at"],
                "completed_at": row["completed_at"]
            }
        return None
    except DatabaseError as e:
        logger.error(f"Failed to get publish job {job_id}: {e}")
        return None


async def process_publish(project_id: str, job_id: str, video_url: str, caption: str, share_to_feed: bool):
    """Background task to publish Reel to Instagram"""
    from infra.integrations.instagram_login import InstagramLoginClient, InstagramLoginError
    from infra.integrations.facebook_instagram_login import FacebookInstagramAuthClient, FacebookInstagramAuthError
    from infra.config.settings import config
    import time
    
    publish_start_time = time.time()
    logger.info(f"Starting publish for project {project_id}, job {job_id}")
    
    try:
        # Update status to publishing
        update_publish_job_status(job_id, "publishing")
        update_project_status(project_id, "publishing")
        
        # Get Instagram credentials - support both Facebook Login (new) and Instagram Login (legacy)
        auth_flow = get_setting("instagram_auth_flow", "")
        
        if auth_flow == "facebook_login":
            # Facebook Login for Business → Instagram flow (new)
            access_token = get_setting("facebook_instagram_long_lived_token") or \
                           get_setting("facebook_instagram_access_token")
            user_id = get_setting("facebook_instagram_business_account_id")
            
            if not access_token or not user_id:
                raise ValueError(
                    "Facebook Instagram connection not complete. "
                    "Missing access token or Instagram Business Account ID."
                )
            
            # Use Facebook-login-aware client with graph.facebook.com endpoints
            client = FacebookInstagramAuthClient()
            result = client.publish_reel(
                instagram_business_account_id=str(user_id),
                access_token=access_token,
                video_url=video_url,
                caption=caption,
                share_to_feed=share_to_feed,
            )
        else:
            # Legacy Instagram Login flow
            access_token = get_setting("instagram_access_token") or config.INSTAGRAM_ACCESS_TOKEN
            user_id = get_setting("instagram_user_id") or getattr(config, 'INSTAGRAM_USER_ID', None)
            
            if not access_token or not user_id:
                raise ValueError("Instagram not connected. Please connect Instagram first.")
            
            # Use legacy InstagramLoginClient with graph.instagram.com endpoints
            client = InstagramLoginClient(
                app_id=config.INSTAGRAM_APP_ID,
                app_secret=config.INSTAGRAM_APP_SECRET,
                redirect_uri=config.INSTAGRAM_REDIRECT_URI or "",
            )
            
            result = client.publish_reel(
                user_id=str(user_id),
                access_token=access_token,
                video_url=video_url,
                caption=caption,
                share_to_feed=share_to_feed,
            )
        
        # Update success
        media_id = result.get("id")
        update_publish_job_status(job_id, "published", external_media_id=media_id)
        update_project_status(project_id, "published")
        
        # Phase 5: Track publish metrics
        publish_duration_ms = (time.time() - publish_start_time) * 1000
        update_reels_metrics("publish", status="published", duration_ms=publish_duration_ms)
        
        logger.info(f"Publish complete for project {project_id}, Instagram media ID: {media_id}")
        
    except (InstagramLoginError, FacebookInstagramAuthError) as e:
        logger.error(f"Instagram publish failed for project {project_id}: {e}")
        update_publish_job_status(job_id, "failed", error_message=str(e))
        update_project_status(project_id, "failed")
        update_reels_metrics("publish", status="failed")
    except Exception as e:
        logger.error(f"Publish failed for project {project_id}: {e}")
        update_publish_job_status(job_id, "failed", error_message=str(e))
        update_project_status(project_id, "failed")
        update_reels_metrics("publish", status="failed")


@router.post("/projects/{project_id}/publish", response_model=PublishResponse)
async def publish_reel(project_id: str, request: PublishRequest, background_tasks: BackgroundTasks):
    """
    Publish a rendered Reel to Instagram.
    Requires Instagram professional account connection.
    """
    project = get_project_db(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check project has rendered video
    if project["status"] != "ready" or not project.get("final_output_url"):
        raise HTTPException(
            status_code=400, 
            detail="Reel not ready for publish. Generate video first."
        )
    
    # Check Instagram connection - support both Facebook Login (new) and Instagram Login (legacy)
    from infra.config.settings import config
    auth_flow = get_setting("instagram_auth_flow", "")
    
    if auth_flow == "facebook_login":
        # Facebook Login for Business flow (new)
        access_token = get_setting("facebook_instagram_long_lived_token") or \
                       get_setting("facebook_instagram_access_token")
        user_id = get_setting("facebook_instagram_business_account_id")
        
        if not access_token or not user_id:
            raise HTTPException(
                status_code=403,
                detail="Facebook Instagram connection not complete. Please reconnect your account."
            )
    else:
        # Legacy Instagram Login flow
        access_token = get_setting("instagram_access_token") or config.INSTAGRAM_ACCESS_TOKEN
        user_id = get_setting("instagram_user_id") or getattr(config, 'INSTAGRAM_USER_ID', None)
        
        if not access_token or not user_id:
            raise HTTPException(
                status_code=403,
                detail="Instagram not connected. Please connect your Instagram professional account first."
            )
    
    # Build full video URL (must be publicly accessible for Instagram)
    video_url = project["final_output_url"]
    if video_url.startswith("/"):
        # Relative URL - need base URL from settings
        base_url = get_setting("reels_public_base_url", "")
        if not base_url:
            raise HTTPException(
                status_code=400,
                detail="Public URL not configured. Please set reels_public_base_url in settings (e.g., https://yourdomain.com)."
            )
        video_url = f"{base_url.rstrip('/')}{video_url}"
    
    # Build caption with hashtags
    caption = request.caption
    hashtags_str = json.dumps(request.hashtags) if request.hashtags else "[]"
    if request.hashtags:
        hashtag_str = " ".join([f"#{h}" for h in request.hashtags])
        caption = f"{caption}\n\n{hashtag_str}".strip()
    
    # Persist caption and hashtags to project
    try:
        execute_insert(
            "UPDATE reel_projects SET caption = ?, hashtags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (caption, hashtags_str, project_id)
        )
    except DatabaseError as e:
        logger.error(f"Failed to persist caption for project {project_id}: {e}")
    
    # Create publish job
    job_id = create_publish_job_db(project_id)
    
    # Queue background publish
    background_tasks.add_task(
        process_publish,
        project_id,
        job_id,
        video_url,
        caption,
        request.share_to_feed
    )
    
    logger.info(f"Queued reel publish job {job_id} for project {project_id}")
    
    return PublishResponse(
        publish_job_id=job_id,
        status="queued",
        message="Reel queued for publishing to Instagram."
    )


@router.get("/projects/{project_id}/publish/{job_id}")
async def get_publish_status(project_id: str, job_id: str):
    """Get publish job status"""
    job = get_publish_job_db(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Publish job not found")
    
    if job["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="Publish job not found for this project")
    
    return job
