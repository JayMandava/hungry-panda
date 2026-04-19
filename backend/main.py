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
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
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
    DatabaseError
)
from config.logging_config import logger

# Import analyzer modules
try:
    from analyzer.content_engine import analyze_and_recommend
    from analyzer.competitor_tracker import analyze_competitor, get_market_insights
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
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "config_valid": config.validate()["valid"],
        "analyzer_available": ANALYZER_AVAILABLE
    }


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
    Validate that the content is food/cooking related.
    Returns True if food-related keywords are found.
    """
    # Food-related keywords
    food_keywords = [
        'food', 'cook', 'recipe', 'dish', 'meal', 'dinner', 'lunch', 'breakfast', 'brunch',
        'pasta', 'pizza', 'curry', 'rice', 'chicken', 'beef', 'pork', 'fish', 'salmon', 'tuna',
        'vegetable', 'salad', 'soup', 'stew', 'grill', 'bake', 'roast', 'fry', 'saute',
        'dessert', 'cake', 'cookie', 'bread', 'pastry', 'pie', 'chocolate', 'sweet',
        'spicy', 'homemade', 'fresh', 'delicious', 'tasty', 'yummy', 'chef', 'kitchen',
        'ingredient', 'spice', 'herb', 'sauce', 'marinade', 'appetizer', 'entree', 'main',
        'vegan', 'vegetarian', 'healthy', 'organic', 'gluten', 'keto', 'paleo',
        'italian', 'indian', 'chinese', 'mexican', 'thai', 'japanese', 'korean',
        'mediterranean', 'french', 'greek', 'spanish', 'asian', 'bbq', 'grilled'
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
    caption: Optional[str] = None,
    context: Optional[str] = None,
    auto_optimize: bool = True
):
    """
    Upload new content for the agent to curate.
    
    - **file**: Photo or video to upload
    - **caption**: Optional user-provided caption hint
    - **context**: Additional context about the content (dish description, recipe, story, etc.)
    - **auto_optimize**: If true, AI will analyze and provide recommendations
    
    Returns upload confirmation and AI recommendations if auto_optimize is enabled.
    
    Note: Hungry Panda only handles food and cooking related content.
    """
    try:
        # Validate file
        allowed_types = ['image/', 'video/']
        if not any(file.content_type.startswith(t) for t in allowed_types):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type: {file.content_type}. Only images and videos allowed."
            )
        
        # Validate food content
        is_food_related = validate_food_content(context, caption, file.filename)
        
        if not is_food_related:
            logger.warning(f"Non-food content rejected: {file.filename}")
            raise HTTPException(
                status_code=400,
                detail="🐼 Hungry Panda only handles food or cooking related content. Please describe your dish in the context field (e.g., 'homemade pasta with basil') or rename your file to include food-related keywords."
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


@app.get("/api/growth/dashboard", response_model=Dict[str, Any])
async def get_dashboard_metrics():
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
        hashtag_data = execute_query(
            "SELECT * FROM hashtag_performance ORDER BY avg_engagement DESC LIMIT 10"
        )
        top_hashtags = [dict(row) for row in hashtag_data]
        
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


@app.get("/api/competitors", response_model=Dict[str, List[Dict]])
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


@app.get("/api/config/profile")
async def get_profile_config():
    """
    Get current Instagram profile configuration (safe info only).
    No sensitive credentials are returned.
    """
    return {
        "username": config.INSTAGRAM_USERNAME,
        "account_type": config.INSTAGRAM_ACCOUNT_TYPE,
        "posting_method": config.POSTING_METHOD,
        "auto_scheduler_enabled": config.AUTO_SCHEDULER_ENABLED,
        "max_posts_per_day": config.MAX_POSTS_PER_DAY,
        "configured": bool(config.INSTAGRAM_USERNAME)
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
