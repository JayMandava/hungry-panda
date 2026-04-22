"""
Hungry Panda - Instagram Growth Agent
Backend API using FastAPI

This module provides the main FastAPI application with all endpoints
for the Instagram growth agent system.
"""
import os
import sys
import json
import hashlib
import random
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import config
from config.database import (
    init_database, 
    get_db_connection, 
    execute_query, 
    execute_insert,
    DatabaseError,
    get_setting,
    set_setting,
)
from config.logging_config import logger
from integrations.instagram_login import (
    DEFAULT_SCOPES,
    InstagramLoginClient,
    InstagramLoginError,
    get_configured_redirect_uri,
)

# Import analyzer modules
try:
    from analyzer.content_engine import analyze_and_recommend, get_recommendation_stats, get_inference_metrics
    from analyzer.competitor_tracker import (
        analyze_competitor,
        get_market_insights,
        get_industry_trending_hashtags,
    )
    from analyzer.strategist import generate_weekly_strategy
    ANALYZER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Analyzer modules not available: {e}")
    ANALYZER_AVAILABLE = False

# FastAPI app
app = FastAPI(
    title="Hungry Panda - Instagram Growth Agent",
    description="AI-powered Instagram growth management for food & cooking accounts",
    version="1.0.0"
)

frontend_assets_dir = Path(__file__).parent.parent / "frontend" / "assets"
if frontend_assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=frontend_assets_dir), name="frontend-assets")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    try:
        init_database()
        logger.info("Application started successfully")
        
        # Validate configuration
        validation = config.validate()
        if not validation["valid"]:
            logger.warning(f"Configuration issues: {validation['issues']}")
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise


# P1: Cleanup on shutdown - close persistent HTTP session
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown"""
    try:
        from integrations.llm_client import LLMClient
        LLMClient.close_session()
        logger.info("HTTP session closed on shutdown")
    except Exception as e:
        logger.warning(f"Error closing HTTP session: {e}")


# Pydantic Models
class ContentUploadRequest(BaseModel):
    """Request model for content upload"""
    caption: Optional[str] = Field(None, description="Optional user-provided caption")
    scheduled_time: Optional[str] = Field(None, description="Optional scheduled time (ISO format)")
    auto_optimize: bool = Field(True, description="Whether to auto-generate recommendations")


class ContentScheduleRequest(BaseModel):
    """Request model for scheduling content"""
    final_caption: str = Field(..., description="Final caption for the post")
    final_hashtags: List[str] = Field(default_factory=list, description="Final hashtags")
    scheduled_time: Optional[str] = Field(None, description="When to post (ISO format)")


class CompetitorAddRequest(BaseModel):
    """Request model for adding competitor"""
    username: str = Field(..., min_length=1, description="Instagram username to track")


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None


def get_fallback_trending_hashtags(limit: int = 10) -> List[Dict[str, Any]]:
    """Return industry-relevant fallback hashtags for the dashboard."""
    if ANALYZER_AVAILABLE:
        try:
            return get_industry_trending_hashtags(limit)
        except Exception as exc:
            logger.warning(f"Fallback hashtag generation failed: {exc}")

    return [
        {"hashtag": "foodandbeverage", "category": "f&b", "avg_engagement": 4.8},
        {"hashtag": "restaurantlife", "category": "restaurant", "avg_engagement": 4.6},
        {"hashtag": "hospitalitylife", "category": "hotel", "avg_engagement": 4.3},
        {"hashtag": "finedining", "category": "restaurant", "avg_engagement": 4.7},
        {"hashtag": "cafevibes", "category": "cafe", "avg_engagement": 4.1},
        {"hashtag": "cocktailculture", "category": "beverage", "avg_engagement": 4.0},
        {"hashtag": "hotelrestaurant", "category": "hotel", "avg_engagement": 4.2},
        {"hashtag": "chefstable", "category": "restaurant", "avg_engagement": 4.5},
        {"hashtag": "foodpresentation", "category": "f&b", "avg_engagement": 4.4},
        {"hashtag": "restaurantmarketing", "category": "business", "avg_engagement": 3.8},
        {"hashtag": "brunchgoals", "category": "restaurant", "avg_engagement": 4.1},
        {"hashtag": "luxurydining", "category": "hotel", "avg_engagement": 3.9},
        {"hashtag": "cheflife", "category": "restaurant", "avg_engagement": 4.0},
        {"hashtag": "platedessert", "category": "restaurant", "avg_engagement": 3.9},
        {"hashtag": "craftcocktails", "category": "beverage", "avg_engagement": 3.8},
        {"hashtag": "weekendbrunch", "category": "cafe", "avg_engagement": 4.0},
        {"hashtag": "boutiquehotel", "category": "hotel", "avg_engagement": 3.7},
        {"hashtag": "tablescape", "category": "f&b", "avg_engagement": 3.9},
        {"hashtag": "restaurantdesign", "category": "business", "avg_engagement": 3.6},
        {"hashtag": "mixologyart", "category": "beverage", "avg_engagement": 3.7},
    ][:limit]


def get_dashboard_top_hashtags(refresh: bool = False, limit: int = 10) -> List[Dict[str, Any]]:
    """Return dashboard hashtags, varying the list when the user explicitly refreshes."""
    hashtag_data = execute_query(
        "SELECT * FROM hashtag_performance ORDER BY avg_engagement DESC LIMIT 30"
    )
    hashtag_pool = [dict(row) for row in hashtag_data]
    if not hashtag_pool:
        hashtag_pool = get_fallback_trending_hashtags(limit=max(limit * 3, 18))

    if not refresh:
        return hashtag_pool[:limit]

    if len(hashtag_pool) <= limit:
        refreshed = hashtag_pool[:]
        random.shuffle(refreshed)
        return refreshed[:limit]

    return random.sample(hashtag_pool, limit)


def build_instagram_status(request: Optional[Request] = None) -> Dict[str, Any]:
    """Build current Instagram connection status from DB settings and env fallback."""
    base_url = str(request.base_url).rstrip("/") if request else None
    redirect_uri = None
    redirect_error = None

    try:
        redirect_uri = get_configured_redirect_uri(base_url)
    except InstagramLoginError as exc:
        redirect_error = str(exc)

    permissions = get_setting("instagram_permissions", "") or ""
    granted_permissions = [p.strip() for p in permissions.split(",") if p.strip()]
    required_permissions = list(DEFAULT_SCOPES)
    missing_permissions = [
        permission for permission in required_permissions if permission not in granted_permissions
    ]

    connected = (get_setting("instagram_connected", "false") == "true")
    account_type = get_setting("instagram_account_type") or config.INSTAGRAM_ACCOUNT_TYPE

    return {
        "connected": connected,
        "oauth_ready": bool(
            config.INSTAGRAM_APP_ID and
            config.INSTAGRAM_APP_SECRET and
            redirect_uri
        ),
        "app_id_configured": bool(config.INSTAGRAM_APP_ID),
        "app_secret_configured": bool(config.INSTAGRAM_APP_SECRET),
        "redirect_uri": redirect_uri,
        "redirect_uri_error": redirect_error,
        "username": get_setting("instagram_username") or config.INSTAGRAM_USERNAME,
        "account_type": account_type,
        "instagram_user_id": get_setting("instagram_user_id") or get_setting("instagram_business_account_id"),
        "token_expires_at": get_setting("instagram_token_expires_at"),
        "last_validated_at": get_setting("instagram_last_validated_at"),
        "permissions": granted_permissions,
        "missing_permissions": missing_permissions,
        "can_publish": account_type in {"Business", "Media_Creator", "business", "creator"} and not missing_permissions,
        "posting_method": config.POSTING_METHOD,
        "connect_url": "/api/instagram/oauth/start" if redirect_uri else None,
    }


def persist_instagram_connection(
    token_payload: Dict[str, Any],
    profile_payload: Dict[str, Any],
) -> None:
    """Persist Instagram connection details in system settings."""
    expires_in = int(token_payload.get("expires_in", 0) or 0)
    expires_at = (
        datetime.utcnow() + timedelta(seconds=expires_in)
    ).isoformat() if expires_in else (get_setting("instagram_token_expires_at") or None)

    permissions = token_payload.get("permissions", "")
    if isinstance(permissions, list):
        permissions = ",".join(permissions)

    values = {
        "instagram_connected": "true",
        "instagram_access_token": token_payload.get("access_token", ""),
        "instagram_token_type": token_payload.get("token_type", "bearer"),
        "instagram_token_expires_at": expires_at or "",
        "instagram_permissions": permissions or "",
        "instagram_username": profile_payload.get("username", ""),
        "instagram_display_name": profile_payload.get("name", ""),
        "instagram_user_id": str(profile_payload.get("user_id", "")),
        "instagram_business_account_id": str(profile_payload.get("user_id", "")),
        "instagram_account_type": profile_payload.get("account_type", ""),
        "instagram_profile_picture_url": profile_payload.get("profile_picture_url", ""),
        "instagram_followers_count": str(profile_payload.get("followers_count", 0) or 0),
        "instagram_follows_count": str(profile_payload.get("follows_count", 0) or 0),
        "instagram_media_count": str(profile_payload.get("media_count", 0) or 0),
        "instagram_last_validated_at": datetime.utcnow().isoformat(),
        "instagram_error": "",
    }

    for key, value in values.items():
        set_setting(key, value)


def clear_instagram_connection(error_message: Optional[str] = None) -> None:
    """Mark the Instagram connection as disconnected without deleting app config."""
    set_setting("instagram_connected", "false")
    if error_message:
        set_setting("instagram_error", error_message)


def resolve_content_filepath(stored_filepath: Optional[str]) -> Optional[Path]:
    """Resolve a stored content filepath across old and current upload locations."""
    if not stored_filepath:
        return None

    candidate = Path(stored_filepath)
    if candidate.exists():
        return candidate

    basename = candidate.name
    fallback_paths = [
        Path(config.UPLOADS_DIR) / basename,
        Path("/tmp/hungry-panda/uploads") / basename,
    ]

    for fallback in fallback_paths:
        if fallback.exists():
            return fallback

    return None


def render_instagram_connect_page(status: Dict[str, Any], message: Optional[str] = None) -> str:
    """Render a small standalone page for Instagram connection management."""
    connect_button = ""
    if status["oauth_ready"]:
        connect_button = (
            '<a href="/api/instagram/oauth/start" '
            'style="display:inline-block;background:#e94560;color:#fff;padding:12px 18px;'
            'border-radius:10px;text-decoration:none;font-weight:600;">Connect Instagram</a>'
        )

    oauth_help = ""
    if not status["oauth_ready"]:
        oauth_help = (
            "<p><strong>Missing config.</strong> Add "
            "<code>INSTAGRAM_APP_ID</code>, <code>INSTAGRAM_APP_SECRET</code>, and "
            "<code>INSTAGRAM_REDIRECT_URI</code> in <code>config/.env</code>."
            "</p>"
        )

    if status.get("redirect_uri"):
        oauth_help += (
            f"<p><strong>Redirect URI to add in Meta App Dashboard:</strong> "
            f"<code>{status['redirect_uri']}</code></p>"
        )

    permissions = ", ".join(status["permissions"]) if status["permissions"] else "None yet"
    missing_permissions = (
        ", ".join(status["missing_permissions"]) if status["missing_permissions"] else "None"
    )
    message_html = f"<p style='color:#4ade80'>{message}</p>" if message else ""

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Instagram Connection - Hungry Panda</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: #0f0f23;
                color: #fff;
                margin: 0;
                padding: 32px 20px;
            }}
            .card {{
                max-width: 760px;
                margin: 0 auto;
                background: #1a1a2e;
                border: 1px solid #2d2d44;
                border-radius: 16px;
                padding: 24px;
            }}
            code {{
                background: #0f0f23;
                padding: 2px 6px;
                border-radius: 6px;
            }}
            .row {{
                margin: 10px 0;
                color: #cbd5e1;
            }}
            .actions {{
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
                margin: 20px 0;
            }}
            button {{
                background: #2d2d44;
                border: none;
                color: #fff;
                padding: 12px 18px;
                border-radius: 10px;
                cursor: pointer;
                font-weight: 600;
            }}
            pre {{
                background: #0f0f23;
                border-radius: 12px;
                padding: 16px;
                overflow-x: auto;
                color: #cbd5e1;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Instagram Connection</h1>
            <p>Use Meta's official Instagram login flow for your professional account.</p>
            {message_html}
            <div class="row"><strong>Connected:</strong> {status["connected"]}</div>
            <div class="row"><strong>Username:</strong> {status["username"] or "Not connected"}</div>
            <div class="row"><strong>Account Type:</strong> {status["account_type"] or "Unknown"}</div>
            <div class="row"><strong>Can Publish:</strong> {status["can_publish"]}</div>
            <div class="row"><strong>Granted Permissions:</strong> {permissions}</div>
            <div class="row"><strong>Missing Permissions:</strong> {missing_permissions}</div>
            <div class="row"><strong>Token Expires:</strong> {status["token_expires_at"] or "Unknown"}</div>
            {oauth_help}
            <div class="actions">
                {connect_button}
                <button onclick="testConnection()">Test Connection</button>
                <button onclick="location.href='/'">Back to Dashboard</button>
            </div>
            <pre id="result">Status will appear here.</pre>
        </div>
        <script>
            async function testConnection() {{
                const result = document.getElementById('result');
                result.textContent = 'Testing...';
                try {{
                    const response = await fetch('/api/instagram/test', {{ method: 'POST' }});
                    const data = await response.json();
                    result.textContent = JSON.stringify(data, null, 2);
                }} catch (error) {{
                    result.textContent = error.message;
                }}
            }}
        </script>
    </body>
    </html>
    """


# Routes

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """
    Serve the main growth dashboard.
    Returns the HTML dashboard for managing the Instagram growth agent.
    """
    dashboard_path = Path(__file__).parent.parent / "frontend" / "dashboard.html"
    
    if dashboard_path.exists():
        return HTMLResponse(content=dashboard_path.read_text())
    
    # Fallback embedded dashboard
    return HTMLResponse(content=get_fallback_dashboard())


@app.get("/voice-styles.css")
async def serve_voice_styles():
    """Serve voice input styles CSS"""
    css_path = Path(__file__).parent.parent / "frontend" / "voice-styles.css"
    if css_path.exists():
        return FileResponse(css_path, media_type="text/css")
    return HTMLResponse(content="/* CSS not found */", status_code=404)


@app.get("/api/health")
async def health_check():
    """Health check endpoint with inference metrics"""
    recommendation_stats = get_recommendation_stats() if ANALYZER_AVAILABLE else {}
    inference_metrics = get_inference_metrics() if ANALYZER_AVAILABLE else {}
    
    # P1: Add visual analysis cache stats if available
    visual_cache_stats = {}
    if ANALYZER_AVAILABLE:
        try:
            from integrations.llm_client import LLMClient
            visual_cache_stats = LLMClient.get_visual_cache_stats()
        except Exception:
            pass
    
    return {
        "status": "healthy",
        "version": "1.0.0",
        "config_valid": config.validate()["valid"],
        "analyzer_available": ANALYZER_AVAILABLE,
        "structured_rec_success_rate": recommendation_stats.get("structured_rec_success_rate"),
        "recommendation_stats": recommendation_stats,
        "inference_metrics": inference_metrics,
        "visual_cache_stats": visual_cache_stats,
    }


@app.get("/api/debug/inference-metrics")
async def debug_inference_metrics():
    """Debug endpoint for detailed inference timing and call counts"""
    if not ANALYZER_AVAILABLE:
        return {"error": "Analyzer not available"}
    return get_inference_metrics()


@app.get("/upload", response_class=HTMLResponse)
async def working_upload_page():
    """Clean working upload page with chat-style bar"""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Upload - Hungry Panda</title>
    <style>
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f23;
            color: #fff;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        h1 {
            font-size: 28px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .subtitle {
            color: #8b8b9a;
            margin-bottom: 30px;
            font-size: 16px;
        }
        
        /* Upload Area */
        .upload-area {
            border: 2px dashed #3d3d5c;
            border-radius: 20px;
            padding: 40px 20px;
            text-align: center;
            background: #1a1a2e;
            margin-bottom: 20px;
            transition: all 0.2s;
        }
        .upload-area.dragover {
            border-color: #e94560;
            background: rgba(233, 69, 96, 0.1);
        }
        .upload-icon {
            font-size: 48px;
            margin-bottom: 15px;
        }
        .upload-text {
            color: #8b8b9a;
            margin-bottom: 20px;
            font-size: 15px;
        }
        .btn-select {
            background: linear-gradient(135deg, #e94560 0%, #d63852 100%);
            border: none;
            color: white;
            padding: 14px 32px;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
        }
        #fileInput { display: none; }
        
        /* File Preview */
        .file-preview {
            display: none;
            background: #1a1a2e;
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .file-preview.active { display: block; }
        .file-name {
            color: #4ade80;
            font-weight: 600;
            margin-bottom: 15px;
            word-break: break-all;
        }
        
        /* Chat-style Input Bar */
        .chat-bar {
            display: flex;
            align-items: center;
            gap: 10px;
            background: #0f0f23;
            border: 2px solid #3d3d5c;
            border-radius: 28px;
            padding: 8px 12px;
        }
        .chat-input {
            flex: 1;
            background: transparent;
            border: none;
            color: #fff;
            font-size: 16px;
            padding: 10px;
            outline: none;
        }
        .chat-input::placeholder {
            color: #5a5a7a;
        }
        .chat-mic, .chat-send {
            width: 44px;
            height: 44px;
            border: none;
            border-radius: 50%;
            cursor: pointer;
            font-size: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }
        .chat-mic {
            background: #2d2d44;
            color: #fff;
        }
        .chat-mic:hover, .chat-mic.recording {
            background: #e94560;
        }
        .chat-mic.recording {
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.1); }
        }
        .chat-send {
            background: linear-gradient(135deg, #e94560 0%, #d63852 100%);
            color: white;
        }
        .chat-send:hover {
            transform: scale(1.05);
        }
        
        /* Recording Status */
        .recording-status {
            display: none;
            align-items: center;
            justify-content: center;
            gap: 8px;
            margin-top: 10px;
            color: #ef4444;
            font-size: 14px;
        }
        .recording-status.active { display: flex; }
        .red-dot {
            width: 8px;
            height: 8px;
            background: #ef4444;
            border-radius: 50%;
            animation: blink 1s infinite;
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        
        /* Toast */
        .toast {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #1a1a2e;
            border: 1px solid #4ade80;
            color: #4ade80;
            padding: 12px 24px;
            border-radius: 8px;
            display: none;
            z-index: 1000;
            font-size: 14px;
        }
        .toast.show { display: block; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🐼 Hungry Panda</h1>
        <p class="subtitle">Upload food photos & get AI recommendations</p>
        
        <!-- Upload Area -->
        <div class="upload-area" id="uploadArea">
            <div class="upload-icon">🍽️</div>
            <div class="upload-text">
                Drop photos here or tap below<br>
                <small>AI will suggest captions & hashtags</small>
            </div>
            <button class="btn-select" onclick="document.getElementById('fileInput').click()">
                📎 Select File
            </button>
            <input type="file" id="fileInput" accept="image/*,video/*">
        </div>
        
        <!-- File Preview & Chat Bar -->
        <div class="file-preview" id="filePreview">
            <div class="file-name" id="fileName"></div>
            
            <div class="chat-bar">
                <input 
                    type="text" 
                    id="contextInput" 
                    class="chat-input" 
                    placeholder="Describe your dish (optional)..."
                >
                <button class="chat-mic" id="micBtn" onclick="toggleVoice()">🎤</button>
                <button class="chat-send" onclick="upload()">⬆️</button>
            </div>
            
            <div class="recording-status" id="recordingStatus">
                <span class="red-dot"></span>
                <span id="recordingText">Listening...</span>
            </div>
        </div>
    </div>
    
    <div class="toast" id="toast"></div>
    
    <script>
        let selectedFile = null;
        let recognition = null;
        let isRecording = false;
        
        // Initialize speech recognition
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = 'en-US';
            
            recognition.onresult = (event) => {
                let transcript = '';
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    transcript += event.results[i][0].transcript;
                }
                if (transcript) {
                    document.getElementById('contextInput').value = transcript;
                    document.getElementById('recordingText').textContent = transcript;
                }
            };
            
            recognition.onerror = () => {
                stopRecording();
                showToast('❌ Voice error - try typing');
            };
        } else {
            document.getElementById('micBtn').style.display = 'none';
        }
        
        // File selection
        document.getElementById('fileInput').addEventListener('change', (e) => {
            if (e.target.files.length) {
                selectedFile = e.target.files[0];
                document.getElementById('fileName').textContent = '📎 ' + selectedFile.name;
                document.getElementById('filePreview').classList.add('active');
                showToast('📎 File selected! Add context & tap ⬆️');
            }
        });
        
        // Drag & drop
        const uploadArea = document.getElementById('uploadArea');
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                selectedFile = e.dataTransfer.files[0];
                document.getElementById('fileName').textContent = '📎 ' + selectedFile.name;
                document.getElementById('filePreview').classList.add('active');
                showToast('📎 File dropped! Add context & tap ⬆️');
            }
        });
        
        // Voice toggle
        function toggleVoice() {
            if (!recognition) {
                showToast('❌ Voice not supported');
                return;
            }
            
            if (isRecording) {
                stopRecording();
            } else {
                startRecording();
            }
        }
        
        function startRecording() {
            isRecording = true;
            recognition.start();
            document.getElementById('micBtn').classList.add('recording');
            document.getElementById('recordingStatus').classList.add('active');
            showToast('🎤 Recording... speak now');
        }
        
        function stopRecording() {
            isRecording = false;
            if (recognition) recognition.stop();
            document.getElementById('micBtn').classList.remove('recording');
            document.getElementById('recordingStatus').classList.remove('active');
        }
        
        // Upload
        async function upload() {
            if (!selectedFile) {
                showToast('❌ Select a file first');
                return;
            }
            
            const context = document.getElementById('contextInput').value;
            const formData = new FormData();
            formData.append('file', selectedFile);
            formData.append('context', context);
            formData.append('auto_optimize', 'true');
            
            showToast('📤 Uploading...');
            
            try {
                const res = await fetch('/api/content/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await res.json();
                
                if (data.recommendation) {
                    // Show results
                    alert('✅ Upload complete!\\n\\nCaption: ' + data.recommendation.suggested_caption + 
                          '\\n\\nHashtags: #' + data.recommendation.suggested_hashtags.slice(0, 5).join(' #'));
                    
                    // Reset
                    selectedFile = null;
                    document.getElementById('contextInput').value = '';
                    document.getElementById('filePreview').classList.remove('active');
                    document.getElementById('fileInput').value = '';
                    showToast('✅ Upload complete!');
                } else {
                    showToast('✅ Uploaded! Check dashboard');
                }
            } catch (err) {
                showToast('❌ Upload failed: ' + err.message);
            }
        }
        
        // Toast
        function showToast(msg) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }
    </script>
</body>
</html>
    """)


@app.post("/simple-upload-submit", response_class=HTMLResponse)
async def simple_upload_submit(
    file: UploadFile = File(...),
    context: Optional[str] = Form(None)
):
    """Simple form upload that returns HTML response"""
    try:
        # Generate unique content ID
        content_id = hashlib.md5(
            f"{file.filename}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        # Save file
        filepath = Path(config.UPLOADS_DIR) / f"{content_id}_{file.filename}"
        content = await file.read()
        
        with open(filepath, "wb") as f:
            f.write(content)
        
        # Store in database
        execute_insert(
            """
            INSERT INTO content (id, filename, filepath, upload_time, caption, context, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (content_id, file.filename, str(filepath), datetime.now().isoformat(), None, context, 'pending')
        )
        
        # Generate AI recommendations
        recommendation_html = ""
        if ANALYZER_AVAILABLE:
            try:
                from analyzer.content_engine import analyze_and_recommend
                recommendation = await analyze_and_recommend(content_id, str(filepath), None, context)
                
                hashtags = ' '.join([f'#{tag}' for tag in recommendation.get('suggested_hashtags', [])[:10]])
                
                recommendation_html = f"""
                <div style="background: #1a1a2e; border: 1px solid #2d2d44; border-radius: 12px; padding: 20px; margin: 20px 0;">
                    <h3 style="color: #e94560; margin-bottom: 15px;">🤖 AI Recommendations</h3>
                    
                    <div style="margin-bottom: 20px;">
                        <strong style="color: #fff;">📝 Suggested Caption:</strong><br>
                        <p style="color: #b4b4c7; margin-top: 8px; line-height: 1.5;">{recommendation.get('suggested_caption', 'N/A')}</p>
                    </div>
                    
                    <div style="margin-bottom: 20px;">
                        <strong style="color: #fff;">🏷️ Hashtags:</strong><br>
                        <p style="color: #4ade80; margin-top: 8px; font-size: 14px;">{hashtags}</p>
                    </div>
                    
                    <div style="margin-bottom: 20px;">
                        <strong style="color: #fff;">⏰ Best Time to Post:</strong><br>
                        <p style="color: #b4b4c7; margin-top: 8px;">{recommendation.get('optimal_time', {}).get('time', '6:00 PM')} - {recommendation.get('optimal_time', {}).get('reasoning', 'Peak engagement time')}</p>
                    </div>
                    
                    <div>
                        <strong style="color: #fff;">🎯 Strategy Notes:</strong><br>
                        <p style="color: #8b8b9a; margin-top: 8px; font-size: 14px; line-height: 1.5;">{recommendation.get('strategy_notes', '').replace(chr(10), '<br>')}</p>
                    </div>
                </div>
                """
            except Exception as e:
                recommendation_html = f"<p style='color: #ef4444;'>AI analysis error: {str(e)}</p>"
        
        return HTMLResponse(content=f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload Complete - Hungry Panda</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f23;
            color: #fff;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1 {{ color: #4ade80; }}
        .success {{
            background: rgba(74, 222, 128, 0.1);
            border: 1px solid #4ade80;
            border-radius: 12px;
            padding: 20px;
            margin: 20px 0;
        }}
        a {{
            display: inline-block;
            margin-top: 20px;
            padding: 15px 30px;
            background: linear-gradient(135deg, #e94560 0%, #d63852 100%);
            color: white;
            text-decoration: none;
            border-radius: 12px;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <h1>✅ Upload Complete!</h1>
    <div class="success">
        <strong>File:</strong> {file.filename}<br>
        <strong>Content ID:</strong> {content_id}
    </div>
    {recommendation_html}
    <a href="/simple-upload">📤 Upload Another Photo</a>
    <a href="/" style="margin-left: 10px; background: #2d2d44;">🏠 Go to Dashboard</a>
</body>
</html>
        """)
    except Exception as e:
        return HTMLResponse(content=f"""
<!DOCTYPE html>
<html><body style="background: #0f0f23; color: #ef4444; padding: 20px;">
<h1>❌ Upload Failed</h1>
<p>{str(e)}</p>
<a href="/simple-upload" style="color: #e94560;">Try Again</a>
</body></html>
        """, status_code=500)


def validate_food_content(context: Optional[str], caption: Optional[str], filename: str) -> bool:
    """
    Validate that the content is food/cooking/dining related.
    Returns True if food, drink, restaurant, or hospitality-related keywords are found.
    """
    # Food & Dining related keywords - expanded for F&B, restaurants, hotels, drinks
    food_keywords = [
        # Food basics
        'food', 'cook', 'recipe', 'dish', 'meal', 'dinner', 'lunch', 'breakfast', 'brunch',
        'pasta', 'pizza', 'curry', 'rice', 'chicken', 'beef', 'pork', 'fish', 'salmon', 'tuna',
        'vegetable', 'salad', 'soup', 'stew', 'grill', 'bake', 'roast', 'fry', 'saute',
        'dessert', 'cake', 'cookie', 'bread', 'pastry', 'pie', 'chocolate', 'sweet',
        'spicy', 'homemade', 'fresh', 'delicious', 'tasty', 'yummy', 'chef', 'kitchen',
        'ingredient', 'spice', 'herb', 'sauce', 'marinade', 'appetizer', 'entree', 'main',
        'vegan', 'vegetarian', 'healthy', 'organic', 'gluten', 'keto', 'paleo',
        'italian', 'indian', 'chinese', 'mexican', 'thai', 'japanese', 'korean',
        'mediterranean', 'french', 'greek', 'spanish', 'asian', 'bbq', 'grilled',
        
        # Drinks & Beverages
        'coffee', 'espresso', 'latte', 'cappuccino', 'americano', 'mocha', 'frappuccino',
        'tea', 'chai', 'matcha', 'bubble tea', 'boba',
        'wine', 'red wine', 'white wine', 'rosé', 'champagne', 'prosecco',
        'beer', 'ale', 'lager', 'ipa', 'stout', 'craft beer',
        'cocktail', 'mocktail', 'martini', 'mojito', 'margarita', 'negroni', 'old fashioned',
        'whiskey', 'whisky', 'bourbon', 'scotch', 'vodka', 'gin', 'rum', 'tequila',
        'juice', 'smoothie', 'milkshake', 'lemonade', 'iced tea',
        'beverage', 'drink', 'beverages', 'drinks', 'brew', 'sip', 'sipping',
        
        # Restaurants & Dining
        'restaurant', 'dining', 'eatery', 'cafe', 'café', 'bistro', 'trattoria', 'osteria',
        'bar', 'pub', 'tavern', 'inn', 'lounge', 'rooftop', 'terrace',
        'hotel', 'resort', 'hospitality', 'room service', 'buffet', 'banquet',
        'menu', 'cuisine', 'gastronomy', 'culinary', 'gourmet', 'fine dining',
        'street food', 'food truck', 'takeaway', 'takeout', 'delivery', 'catering',
        'brasserie', 'deli', 'delicatessen', 'patisserie', 'bakery', 'butcher',
        'farm to table', 'organic', 'locally sourced', 'seasonal', 'artisan',
        
        # Food Business/F&B
        'f&b', 'food and beverage', 'food service', 'hospitality industry',
        'restaurant life', 'chef life', 'kitchen life', 'line cook', 'sous chef',
        'foodie', 'food photography', 'food blogger', 'food influencer', 'food content',
        'tasting', 'pairing', 'plating', 'presentation', 'ambiance', 'atmosphere',
        
        # Ingredients & More
        'cheese', 'charcuterie', 'seafood', 'sushi', 'sashimi', 'ramen', 'noodles',
        'dumplings', 'tacos', 'burrito', 'burger', 'sandwich', 'wrap', 'bowl',
        'breakfast', 'brunch', 'lunch', 'dinner', 'supper', 'feast', 'spread',
        'snack', 'appetizer', 'starter', 'mains', 'dessert', 'sweets', 'treat'
    ]
    
    # Combine all text to check
    text_to_check = ' '.join([
        (context or '').lower(),
        (caption or '').lower(),
        filename.lower()
    ])
    
    # Check for food keywords
    for keyword in food_keywords:
        if keyword in text_to_check:
            return True
    
    return False


@app.post("/api/content/upload", response_model=Dict[str, Any])
async def upload_content(
    file: UploadFile = File(..., description="Image or video file to upload"),
    caption: Optional[str] = Form(None),
    context: Optional[str] = Form(None),
    auto_optimize: bool = Form(True)
):
    """
    Upload new content for the agent to curate.
    
    - **file**: Photo or video to upload
    - **caption**: Optional user-provided caption hint
    - **context**: Additional context about the content (dish description, recipe, story, etc.)
    - **auto_optimize**: If true, AI will analyze and provide recommendations
    
    Returns upload confirmation and AI recommendations if auto_optimize is enabled.
    """
    try:
        logger.info(f"Upload request received: file={file.filename}, context={context}, caption={caption}")
        
        # Validate file
        allowed_types = ['image/', 'video/']
        if not any(file.content_type.startswith(t) for t in allowed_types):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type: {file.content_type}. Only images and videos allowed."
            )
        
        # Generate unique content ID
        content_id = hashlib.md5(
            f"{file.filename}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        # Save file
        filepath = Path(config.UPLOADS_DIR) / f"{content_id}_{file.filename}"
        content = await file.read()
        
        with open(filepath, "wb") as f:
            f.write(content)
        
        logger.info(f"Content uploaded: {content_id} ({file.filename})")
        
        # Store in database
        execute_insert(
            """
            INSERT INTO content (id, filename, filepath, upload_time, caption, context, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (content_id, file.filename, str(filepath), datetime.now().isoformat(), caption, context, 'pending')
        )
        
        response = {
            "content_id": content_id,
            "status": "uploaded",
            "filename": file.filename,
            "filepath": str(filepath)
        }
        
        # Generate AI recommendations if enabled
        if auto_optimize and ANALYZER_AVAILABLE:
            try:
                recommendation = await analyze_and_recommend(content_id, str(filepath), caption, context)
                response["recommendation"] = recommendation
                logger.info(f"AI recommendation generated for {content_id}")
            except Exception as e:
                logger.error(f"AI recommendation failed: {e}")
                response["recommendation_warning"] = "AI analysis failed, but content was uploaded"
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/content/pending", response_model=Dict[str, List[Dict]])
async def get_pending_content():
    """
    Get all content waiting for curation/posting.
    Returns pending and scheduled content sorted by upload time.
    """
    try:
        rows = execute_query(
            "SELECT * FROM content WHERE status IN ('pending', 'scheduled') ORDER BY upload_time DESC"
        )
        
        content_list = []
        for row in rows:
            item = dict(row)
            # Parse JSON fields
            if item.get('hashtags'):
                try:
                    item['hashtags'] = json.loads(item['hashtags'])
                except json.JSONDecodeError:
                    item['hashtags'] = []
            content_list.append(item)
        
        return {"pending": content_list}
        
    except DatabaseError as e:
        logger.error(f"Database error fetching pending content: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch content")


@app.get("/api/content/{content_id}/recommendation", response_model=Dict[str, Any])
async def get_content_recommendation(content_id: str):
    """
    Generate or refresh AI recommendations for an already uploaded content item.

    - **content_id**: ID of the uploaded content item
    """
    if not ANALYZER_AVAILABLE:
        raise HTTPException(status_code=503, detail="AI analyzer not available")

    try:
        rows = execute_query(
            """
            SELECT id, filepath, caption, context
            FROM content
            WHERE id = ?
            LIMIT 1
            """,
            (content_id,),
        )

        if not rows:
            raise HTTPException(status_code=404, detail="Content not found")

        item = dict(rows[0])
        resolved_filepath = resolve_content_filepath(item.get("filepath"))
        if not resolved_filepath:
            raise HTTPException(status_code=404, detail="Uploaded file not found")

        if item.get("filepath") != str(resolved_filepath):
            execute_insert(
                "UPDATE content SET filepath = ? WHERE id = ?",
                (str(resolved_filepath), content_id),
            )

        recommendation = await analyze_and_recommend(
            content_id,
            str(resolved_filepath),
            item.get("caption"),
            item.get("context"),
        )

        return recommendation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Recommendation fetch error for {content_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendation: {str(e)}")


@app.post("/api/content/{content_id}/hashtags/refresh", response_model=Dict[str, Any])
async def refresh_content_hashtags(content_id: str):
    """
    Regenerate hashtag variants for an uploaded content item while keeping the recommendation modal open.

    - **content_id**: ID of the uploaded content item
    """
    if not ANALYZER_AVAILABLE:
        raise HTTPException(status_code=503, detail="AI analyzer not available")

    try:
        rows = execute_query(
            """
            SELECT id, filepath, caption, context
            FROM content
            WHERE id = ?
            LIMIT 1
            """,
            (content_id,),
        )

        if not rows:
            raise HTTPException(status_code=404, detail="Content not found")

        item = dict(rows[0])
        resolved_filepath = resolve_content_filepath(item.get("filepath"))
        if not resolved_filepath:
            raise HTTPException(status_code=404, detail="Uploaded file not found")

        recommendation = await analyze_and_recommend(
            content_id,
            str(resolved_filepath),
            item.get("caption"),
            item.get("context"),
        )

        return {
            "content_id": content_id,
            "suggested_hashtags": recommendation.get("suggested_hashtags", []),
            "hashtag_variants": recommendation.get("hashtag_variants", []),
            "confidence_score": recommendation.get("confidence_score"),
            "confidence_reasoning": recommendation.get("confidence_reasoning"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hashtag refresh error for {content_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh hashtags: {str(e)}")


@app.post("/api/content/{content_id}/schedule", response_model=Dict[str, str])
async def schedule_content(content_id: str, schedule_data: ContentScheduleRequest):
    """
    Schedule content for posting.

    - **content_id**: ID of the content to schedule
    - **final_caption**: Caption to use for the post
    - **final_hashtags**: List of hashtags to include
    - **scheduled_time**: ISO timestamp of when to post (optional, defaults to optimal time)
    """
    try:
        # Validate content exists
        rows = execute_query(
            "SELECT id FROM content WHERE id = ?",
            (content_id,)
        )

        if not rows:
            raise HTTPException(status_code=404, detail="Content not found")

        # Use provided time or default to tomorrow at optimal time
        scheduled_time = schedule_data.scheduled_time
        if not scheduled_time:
            scheduled_time = (datetime.now() + timedelta(days=1)).replace(
                hour=18, minute=0, second=0
            ).isoformat()

        # Update database
        execute_insert(
            """
            UPDATE content
            SET scheduled_time = ?, caption = ?, hashtags = ?, status = 'scheduled'
            WHERE id = ?
            """,
            (
                scheduled_time,
                schedule_data.final_caption,
                json.dumps(schedule_data.final_hashtags),
                content_id
            )
        )

        logger.info(f"Content scheduled: {content_id} for {scheduled_time}")

        return {
            "status": "scheduled",
            "content_id": content_id,
            "scheduled_time": scheduled_time
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scheduling error: {e}")
        raise HTTPException(status_code=500, detail=f"Scheduling failed: {str(e)}")


@app.delete("/api/content/{content_id}", response_model=Dict[str, str])
async def delete_content(content_id: str):
    """
    Delete content from the queue.

    - **content_id**: ID of the content to delete
    """
    try:
        # Validate content exists
        rows = execute_query(
            "SELECT id, filepath FROM content WHERE id = ?",
            (content_id,)
        )

        if not rows:
            raise HTTPException(status_code=404, detail="Content not found")

        content = dict(rows[0])
        resolved_filepath = resolve_content_filepath(content.get('filepath'))

        # Delete from database
        execute_insert(
            "DELETE FROM content WHERE id = ?",
            (content_id,)
        )

        # Delete file if it exists
        if resolved_filepath and resolved_filepath.exists():
            try:
                os.remove(resolved_filepath)
                logger.info(f"Deleted file: {resolved_filepath}")
            except OSError as e:
                logger.warning(f"Failed to delete file {resolved_filepath}: {e}")

        logger.info(f"Content deleted: {content_id}")

        return {
            "status": "deleted",
            "content_id": content_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@app.get("/api/growth/dashboard", response_model=Dict[str, Any])
async def get_dashboard_metrics(refresh: Optional[str] = None):
    """
    Get all metrics for the growth dashboard.
    
    Returns comprehensive metrics including:
    - Growth trend (last 30 days)
    - Content stats (total, posted, pending)
    - Top performing hashtags
    - Current strategy recommendations
    - Follower metrics
    """
    try:
        # Get growth metrics (last 30 days)
        growth_data = execute_query(
            """
            SELECT * FROM growth_metrics 
            WHERE date >= date('now', '-30 days')
            ORDER BY date DESC
            """
        )
        growth_list = [dict(row) for row in growth_data]
        
        # Get content stats
        content_stats = execute_query(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status='posted' THEN 1 ELSE 0 END) as posted,
                SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status='scheduled' THEN 1 ELSE 0 END) as scheduled
            FROM content
            """
        )
        stats = dict(content_stats[0]) if content_stats else {
            "total": 0, "posted": 0, "pending": 0, "scheduled": 0
        }
        
        # Get top performing hashtags
        top_hashtags = get_dashboard_top_hashtags(refresh=bool(refresh), limit=10)
        
        # Get latest strategy
        strategy_data = execute_query(
            "SELECT * FROM strategy_recommendations ORDER BY created_at DESC LIMIT 1"
        )
        current_strategy = dict(strategy_data[0]) if strategy_data else None
        
        # Calculate follower metrics
        current_followers = growth_list[0]["followers"] if growth_list else 0
        followers_30d_ago = growth_list[-1]["followers"] if len(growth_list) > 1 else current_followers
        
        return {
            "growth_trend": growth_list,
            "content_stats": stats,
            "top_hashtags": top_hashtags,
            "current_strategy": current_strategy,
            "followers_current": current_followers,
            "followers_30d_ago": followers_30d_ago,
            "growth_30d": current_followers - followers_30d_ago,
            "config_valid": config.validate()["valid"]
        }
        
    except DatabaseError as e:
        logger.error(f"Dashboard metrics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load dashboard data")


@app.post("/api/competitors/add", response_model=Dict[str, str])
async def add_competitor(competitor: CompetitorAddRequest):
    """
    Add a competitor account to track.
    
    The agent will analyze this account to extract insights about
    content patterns, hashtags, and engagement strategies.
    """
    if not config.ENABLE_COMPETITOR_TRACKING:
        raise HTTPException(status_code=403, detail="Competitor tracking is disabled")
    
    try:
        username = competitor.username.strip().replace("@", "")
        
        if not ANALYZER_AVAILABLE:
            # Store without analysis for now
            execute_insert(
                """
                INSERT OR REPLACE INTO competitors (username, last_analyzed)
                VALUES (?, ?)
                """,
                (username, datetime.now().isoformat())
            )
            return {
                "status": "added_pending_analysis",
                "competitor": username,
                "message": "Competitor added. Analysis will run shortly."
            }
        
        # Analyze competitor
        result = await analyze_competitor(username)
        
        execute_insert(
            """
            INSERT OR REPLACE INTO competitors 
            (username, follower_count, avg_engagement, last_analyzed, top_hashtags, content_patterns)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                result.get('followers', 0),
                result.get('avg_engagement', 0),
                datetime.now().isoformat(),
                json.dumps(result.get('top_hashtags', [])),
                json.dumps(result.get('patterns', []))
            )
        )
        
        logger.info(f"Competitor added and analyzed: {username}")
        
        return {
            "status": "added",
            "competitor": username,
            "followers": result.get('followers', 0),
            "engagement": result.get('avg_engagement', 0)
        }
        
    except Exception as e:
        logger.error(f"Add competitor error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add competitor: {str(e)}")


@app.get("/api/competitors", response_model=Dict[str, Any])
async def get_competitors():
    """Get all tracked competitors with their insights"""
    try:
        rows = execute_query(
            "SELECT * FROM competitors ORDER BY avg_engagement DESC"
        )
        
        competitors = []
        for row in rows:
            comp = dict(row)
            # Parse JSON fields
            for field in ['top_hashtags', 'content_patterns']:
                if comp.get(field):
                    try:
                        comp[field] = json.loads(comp[field])
                    except json.JSONDecodeError:
                        comp[field] = []
            competitors.append(comp)
        
        # Add market insights
        if ANALYZER_AVAILABLE:
            try:
                market_insights = get_market_insights()
            except Exception:
                market_insights = {"status": "analysis_pending"}
        else:
            market_insights = {"status": "analyzer_not_available"}
        
        return {
            "competitors": competitors,
            "market_insights": market_insights
        }
        
    except DatabaseError as e:
        logger.error(f"Get competitors error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load competitors")


@app.get("/api/competitors/{username}", response_model=Dict[str, Any])
async def get_competitor_detail(username: str):
    """Get detailed competitor analytics for modal display."""
    if not config.ENABLE_COMPETITOR_TRACKING:
        raise HTTPException(status_code=403, detail="Competitor tracking is disabled")

    normalized = username.strip().replace("@", "")
    if not normalized:
        raise HTTPException(status_code=400, detail="Username is required")

    try:
        if ANALYZER_AVAILABLE:
            detail = await analyze_competitor(normalized)
        else:
            detail = {
                "username": normalized,
                "followers": 0,
                "avg_engagement": 0,
                "content_style": "Analyzer unavailable",
                "top_hashtags": [],
                "patterns": [],
                "posting_frequency": "Unknown",
                "caption_approach": "Unknown",
            }

        rows = execute_query(
            """
            SELECT username, follower_count, avg_engagement, last_analyzed, top_hashtags, content_patterns
            FROM competitors
            WHERE username = ?
            LIMIT 1
            """,
            (normalized,),
        )

        stored = dict(rows[0]) if rows else {}
        for field in ["top_hashtags", "content_patterns"]:
            value = stored.get(field)
            if value:
                try:
                    stored[field] = json.loads(value)
                except json.JSONDecodeError:
                    stored[field] = []

        return {
            "username": normalized,
            "followers": detail.get("followers", stored.get("follower_count", 0)),
            "avg_engagement": detail.get("avg_engagement", stored.get("avg_engagement", 0)),
            "content_style": detail.get("content_style", "Unknown"),
            "top_hashtags": detail.get("top_hashtags") or stored.get("top_hashtags", []),
            "patterns": detail.get("patterns") or stored.get("content_patterns", []),
            "posting_frequency": detail.get("posting_frequency", "Unknown"),
            "caption_approach": detail.get("caption_approach", "Unknown"),
            "last_analyzed": stored.get("last_analyzed"),
            "summary": (
                f"@{normalized} is performing at "
                f"{detail.get('avg_engagement', stored.get('avg_engagement', 0))}% engagement "
                f"with {detail.get('posting_frequency', 'unknown')} posting cadence."
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Competitor detail error for {normalized}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load competitor detail: {str(e)}")


@app.post("/api/strategy/generate", response_model=Dict[str, Any])
async def generate_strategy():
    """
    Generate new content strategy based on analysis.
    
    This creates a weekly strategy including:
    - Content theme for the week
    - Recommended hashtags
    - Optimal posting times
    - Competitor insights
    - Growth action items
    """
    if not ANALYZER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Strategy generator not available")
    
    try:
        strategy = await generate_weekly_strategy()
        
        # Store in database
        execute_insert(
            """
            INSERT INTO strategy_recommendations 
            (created_at, content_theme, recommended_hashtags, optimal_times, competitor_insights, growth_actions, week_starting)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(),
                strategy.get('theme', 'General'),
                json.dumps(strategy.get('hashtags', {})),
                json.dumps(strategy.get('content_calendar', [])),
                json.dumps(strategy.get('insights', [])),
                json.dumps(strategy.get('growth_actions', [])),
                datetime.now().date().isoformat()
            )
        )
        
        logger.info(f"New strategy generated: {strategy.get('theme')}")
        
        return strategy
        
    except Exception as e:
        logger.error(f"Strategy generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Strategy generation failed: {str(e)}")


@app.get("/api/analytics/content-performance")
async def get_content_performance():
    """Get performance data for posted content"""
    try:
        rows = execute_query(
            """
            SELECT * FROM content 
            WHERE status = 'posted' 
            ORDER BY posted_time DESC 
            LIMIT 20
            """
        )
        
        posts = []
        for row in rows:
            post = dict(row)
            if post.get('hashtags'):
                try:
                    post['hashtags'] = json.loads(post['hashtags'])
                except json.JSONDecodeError:
                    post['hashtags'] = []
            posts.append(post)
        
        return {"posts": posts}
        
    except DatabaseError as e:
        logger.error(f"Content performance error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load performance data")


@app.get("/instagram/connect", response_class=HTMLResponse)
async def instagram_connect_page(request: Request):
    """Standalone page for connecting and testing Instagram login."""
    status = build_instagram_status(request)
    message = get_setting("instagram_error")
    return HTMLResponse(render_instagram_connect_page(status, message=message))


@app.get("/api/instagram/status")
async def instagram_status(request: Request):
    """Return current Instagram connection status."""
    return build_instagram_status(request)


@app.get("/api/instagram/oauth/start")
async def instagram_oauth_start(request: Request):
    """Start the Instagram OAuth flow using the official Instagram login."""
    status = build_instagram_status(request)
    if not status["oauth_ready"]:
        raise HTTPException(
            status_code=400,
            detail="Instagram login is not configured. Set INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET, and INSTAGRAM_REDIRECT_URI.",
        )

    state = secrets.token_urlsafe(24)
    set_setting("instagram_oauth_state", state)
    set_setting("instagram_oauth_state_created_at", datetime.utcnow().isoformat())

    client = InstagramLoginClient.from_redirect_uri(status["redirect_uri"])
    return RedirectResponse(client.build_authorization_url(state))


@app.get("/api/instagram/oauth/callback", response_class=HTMLResponse)
async def instagram_oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    """Handle the Instagram OAuth callback and persist the connection."""
    status = build_instagram_status(request)

    if error:
        message = error_description or error
        clear_instagram_connection(message)
        return HTMLResponse(
            render_instagram_connect_page(status, message=f"Instagram connection failed: {message}"),
            status_code=400,
        )

    expected_state = get_setting("instagram_oauth_state")
    if not code or not state or state != expected_state:
        clear_instagram_connection("Invalid or missing OAuth state.")
        return HTMLResponse(
            render_instagram_connect_page(status, message="Instagram connection failed: invalid OAuth state."),
            status_code=400,
        )

    try:
        client = InstagramLoginClient.from_redirect_uri(status["redirect_uri"])
        clean_code = code.replace("#_", "")
        short_lived = client.exchange_code(clean_code)
        long_lived = client.exchange_for_long_lived_token(short_lived["access_token"])

        permissions = short_lived.get("permissions")
        if permissions:
            long_lived["permissions"] = permissions

        profile = client.get_profile(long_lived["access_token"])
        persist_instagram_connection(long_lived, profile)
        refreshed_status = build_instagram_status(request)

        return HTMLResponse(
            render_instagram_connect_page(
                refreshed_status,
                message=f"Connected as @{profile.get('username', 'unknown')}.",
            )
        )
    except InstagramLoginError as exc:
        logger.error(f"Instagram OAuth callback failed: {exc}")
        clear_instagram_connection(str(exc))
        return HTMLResponse(
            render_instagram_connect_page(status, message=f"Instagram connection failed: {exc}"),
            status_code=400,
        )


@app.post("/api/instagram/test")
async def instagram_test_connection(request: Request):
    """Validate the stored Instagram token and return current profile details."""
    access_token = get_setting("instagram_access_token") or config.INSTAGRAM_ACCESS_TOKEN
    if not access_token:
        raise HTTPException(status_code=400, detail="No Instagram access token is configured.")

    status = build_instagram_status(request)
    if not status["redirect_uri"]:
        raise HTTPException(status_code=400, detail="INSTAGRAM_REDIRECT_URI is not configured.")

    try:
        client = InstagramLoginClient.from_redirect_uri(status["redirect_uri"])
        profile = client.get_profile(access_token)
        publishing_limit = None
        publishing_limit_error = None
        try:
            publishing_limit = client.get_content_publishing_limit(str(profile["user_id"]), access_token)
        except InstagramLoginError as exc:
            publishing_limit_error = str(exc)

        persist_instagram_connection(
            {
                "access_token": access_token,
                "token_type": get_setting("instagram_token_type") or "bearer",
                "expires_in": 0,
                "permissions": get_setting("instagram_permissions", ""),
            },
            profile,
        )

        return {
            "connected": True,
            "profile": profile,
            "publishing_limit": publishing_limit,
            "publishing_limit_error": publishing_limit_error,
            "checked_at": datetime.utcnow().isoformat(),
        }
    except InstagramLoginError as exc:
        clear_instagram_connection(str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/config/profile")
async def get_profile_config():
    """
    Get current Instagram profile configuration (safe info only).
    No sensitive credentials are returned.
    """
    username = get_setting("instagram_username") or config.INSTAGRAM_USERNAME
    account_type = get_setting("instagram_account_type") or config.INSTAGRAM_ACCOUNT_TYPE
    connected = get_setting("instagram_connected", "false") == "true"

    return {
        "username": username,
        "account_type": account_type,
        "posting_method": config.POSTING_METHOD,
        "auto_scheduler_enabled": config.AUTO_SCHEDULER_ENABLED,
        "max_posts_per_day": config.MAX_POSTS_PER_DAY,
        "configured": bool(username),
        "instagram_connected": connected,
    }


# Error handlers
@app.exception_handler(DatabaseError)
async def database_exception_handler(request: Request, exc: DatabaseError):
    """Handle database errors"""
    logger.error(f"Database error in {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Database operation failed", "detail": str(exc)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    logger.exception(f"Unhandled error in {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": "An unexpected error occurred"}
    )


def get_fallback_dashboard() -> str:
    """Fallback dashboard HTML if file not found"""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Hungry Panda</title></head>
    <body>
        <h1>🐼 Hungry Panda</h1>
        <p>Dashboard file not found. Please ensure frontend/dashboard.html exists.</p>
        <p>API is running. Visit <a href="/docs">API Documentation</a></p>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting Hungry Panda on {config.HOST}:{config.PORT}")
    uvicorn.run(app, host=config.HOST, port=config.PORT, reload=config.DEBUG)
