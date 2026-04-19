"""
Hungry Panda - Instagram Growth Agent
Backend API using FastAPI
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import os
import sqlite3
import hashlib

app = FastAPI(title="Hungry Panda - Instagram Growth Agent")

# Database setup
def init_db():
    conn = sqlite3.connect('hungry_panda.db')
    c = conn.cursor()
    
    # Content table - stores uploaded photos/videos with metadata
    c.execute('''
        CREATE TABLE IF NOT EXISTS content (
            id TEXT PRIMARY KEY,
            filename TEXT,
            filepath TEXT,
            upload_time TIMESTAMP,
            caption TEXT,
            hashtags TEXT,
            scheduled_time TIMESTAMP,
            posted_time TIMESTAMP,
            status TEXT DEFAULT 'pending',
            engagement_score REAL,
            likes INTEGER,
            comments INTEGER,
            saves INTEGER
        )
    ''')
    
    # Competitors table - tracks competitor accounts
    c.execute('''
        CREATE TABLE IF NOT EXISTS competitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            follower_count INTEGER,
            avg_engagement REAL,
            last_analyzed TIMESTAMP,
            top_hashtags TEXT,
            content_patterns TEXT
        )
    ''')
    
    # Growth metrics table - tracks daily stats
    c.execute('''
        CREATE TABLE IF NOT EXISTS growth_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE,
            followers INTEGER,
            posts INTEGER,
            avg_likes REAL,
            avg_comments REAL,
            reach INTEGER,
            profile_visits INTEGER
        )
    ''')
    
    # Hashtag performance table
    c.execute('''
        CREATE TABLE IF NOT EXISTS hashtag_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hashtag TEXT UNIQUE,
            category TEXT,
            avg_engagement REAL,
            usage_count INTEGER,
            last_used TIMESTAMP
        )
    ''')
    
    # Strategy recommendations table
    c.execute('''
        CREATE TABLE IF NOT EXISTS strategy_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP,
            content_theme TEXT,
            recommended_hashtags TEXT,
            optimal_times TEXT,
            competitor_insights TEXT,
            applied BOOLEAN DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Static files for uploads
os.makedirs("uploads", exist_ok=True)
os.makedirs("static", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Pydantic Models
class ContentUpload(BaseModel):
    caption: Optional[str] = None
    scheduled_time: Optional[str] = None
    auto_optimize: bool = True

class ContentRecommendation(BaseModel):
    content_id: str
    suggested_caption: str
    suggested_hashtags: List[str]
    optimal_time: str
    strategy_notes: str
    confidence_score: float

class CompetitorAdd(BaseModel):
    username: str

class GrowthReport(BaseModel):
    period_days: int = 30

class StrategyInsight(BaseModel):
    theme: str
    reasoning: str
    recommended_actions: List[str]

# Routes

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the main growth dashboard"""
    return HTMLResponse(content=open("frontend/dashboard.html").read() if os.path.exists("frontend/dashboard.html") else dashboard_html())

@app.post("/api/content/upload")
async def upload_content(
    file: UploadFile = File(...),
    caption: Optional[str] = None,
    auto_optimize: bool = True
):
    """Upload new content for the agent to curate"""
    content_id = hashlib.md5(f"{file.filename}{datetime.now()}".encode()).hexdigest()[:12]
    filepath = f"uploads/{content_id}_{file.filename}"
    
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)
    
    conn = sqlite3.connect('hungry_panda.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO content (id, filename, filepath, upload_time, caption, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (content_id, file.filename, filepath, datetime.now(), caption, 'pending'))
    conn.commit()
    conn.close()
    
    if auto_optimize:
        # Trigger AI analysis
        from analyzer.content_engine import analyze_and_recommend
        recommendation = await analyze_and_recommend(content_id, filepath, caption)
        return {
            "content_id": content_id,
            "status": "uploaded",
            "recommendation": recommendation
        }
    
    return {"content_id": content_id, "status": "uploaded"}

@app.get("/api/content/pending")
async def get_pending_content():
    """Get all content waiting for curation/posting"""
    conn = sqlite3.connect('hungry_panda.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM content WHERE status IN ('pending', 'scheduled') ORDER BY upload_time DESC")
    rows = c.fetchall()
    conn.close()
    return {"pending": [dict(row) for row in rows]}

@app.post("/api/content/{content_id}/schedule")
async def schedule_content(content_id: str, schedule_data: dict):
    """Schedule content for posting"""
    scheduled_time = schedule_data.get('scheduled_time')
    final_caption = schedule_data.get('final_caption')
    final_hashtags = schedule_data.get('final_hashtags', [])
    
    conn = sqlite3.connect('hungry_panda.db')
    c = conn.cursor()
    c.execute('''
        UPDATE content 
        SET scheduled_time = ?, caption = ?, hashtags = ?, status = 'scheduled'
        WHERE id = ?
    ''', (scheduled_time, final_caption, json.dumps(final_hashtags), content_id))
    conn.commit()
    conn.close()
    
    return {"status": "scheduled", "content_id": content_id}

@app.get("/api/growth/dashboard")
async def get_dashboard_metrics():
    """Get all metrics for the growth dashboard"""
    conn = sqlite3.connect('hungry_panda.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get growth metrics (last 30 days)
    c.execute("SELECT * FROM growth_metrics ORDER BY date DESC LIMIT 30")
    growth_data = [dict(row) for row in c.fetchall()]
    
    # Get content stats
    c.execute("SELECT COUNT(*) as total, SUM(CASE WHEN status='posted' THEN 1 ELSE 0 END) as posted FROM content")
    content_stats = dict(c.fetchone())
    
    # Get top performing hashtags
    c.execute("SELECT * FROM hashtag_performance ORDER BY avg_engagement DESC LIMIT 10")
    top_hashtags = [dict(row) for row in c.fetchall()]
    
    # Get latest strategy
    c.execute("SELECT * FROM strategy_recommendations ORDER BY created_at DESC LIMIT 1")
    strategy = dict(c.fetchone()) if c.fetchone() else None
    
    conn.close()
    
    return {
        "growth_trend": growth_data,
        "content_stats": content_stats,
        "top_hashtags": top_hashtags,
        "current_strategy": strategy,
        "followers_current": growth_data[0]['followers'] if growth_data else 0,
        "followers_30d_ago": growth_data[-1]['followers'] if len(growth_data) > 1 else 0
    }

@app.post("/api/competitors/add")
async def add_competitor(competitor: CompetitorAdd):
    """Add a competitor account to track"""
    from analyzer.competitor_tracker import analyze_competitor
    
    result = await analyze_competitor(competitor.username)
    
    conn = sqlite3.connect('hungry_panda.db')
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO competitors 
        (username, follower_count, avg_engagement, last_analyzed, top_hashtags, content_patterns)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        competitor.username,
        result.get('followers', 0),
        result.get('avg_engagement', 0),
        datetime.now(),
        json.dumps(result.get('top_hashtags', [])),
        json.dumps(result.get('patterns', []))
    ))
    conn.commit()
    conn.close()
    
    return {"status": "added", "competitor": competitor.username}

@app.get("/api/competitors")
async def get_competitors():
    """Get all tracked competitors with insights"""
    conn = sqlite3.connect('hungry_panda.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM competitors ORDER BY avg_engagement DESC")
    competitors = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"competitors": competitors}

@app.post("/api/strategy/generate")
async def generate_strategy():
    """Generate new content strategy based on analysis"""
    from analyzer.strategist import generate_weekly_strategy
    
    strategy = await generate_weekly_strategy()
    
    conn = sqlite3.connect('hungry_panda.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO strategy_recommendations 
        (created_at, content_theme, recommended_hashtags, optimal_times, competitor_insights)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        datetime.now(),
        strategy['theme'],
        json.dumps(strategy['hashtags']),
        json.dumps(strategy['optimal_times']),
        json.dumps(strategy['insights'])
    ))
    conn.commit()
    conn.close()
    
    return strategy

@app.get("/api/analytics/content-performance")
async def get_content_performance():
    """Get performance data for posted content"""
    conn = sqlite3.connect('hungry_panda.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM content WHERE status = 'posted' ORDER BY posted_time DESC LIMIT 20")
    posts = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"posts": posts}

def dashboard_html():
    """Fallback dashboard HTML"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Hungry Panda - Instagram Growth Agent</title>
        <style>
            body { font-family: system-ui; max-width: 1200px; margin: 0 auto; padding: 20px; }
            .header { background: #1a1a2e; color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }
            .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
            .metric-card { background: #f0f0f0; padding: 20px; border-radius: 8px; text-align: center; }
            .metric-value { font-size: 32px; font-weight: bold; color: #1a1a2e; }
            .section { background: white; border: 1px solid #ddd; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            button { background: #e94560; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; }
            button:hover { background: #c73e54; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🐼 Hungry Panda</h1>
            <p>Instagram Growth Agent for Food & Cooking</p>
        </div>
        <div class="metrics">
            <div class="metric-card">
                <div class="metric-value" id="followers">-</div>
                <div>Followers</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="growth">-</div>
                <div>30d Growth</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="posts">-</div>
                <div>Posts Queued</div>
            </div>
        </div>
        <div class="section">
            <h2>Upload Content</h2>
            <input type="file" id="fileInput" accept="image/*,video/*"><br><br>
            <button onclick="upload()">Upload & Analyze</button>
        </div>
        <script>
            async function loadMetrics() {
                const res = await fetch('/api/growth/dashboard');
                const data = await res.json();
                document.getElementById('followers').textContent = data.followers_current || 0;
                document.getElementById('posts').textContent = data.content_stats?.total || 0;
                const growth = data.followers_current - data.followers_30d_ago;
                document.getElementById('growth').textContent = (growth > 0 ? '+' : '') + growth;
            }
            async function upload() {
                const file = document.getElementById('fileInput').files[0];
                if (!file) return alert('Select a file');
                const form = new FormData();
                form.append('file', file);
                form.append('auto_optimize', 'true');
                const res = await fetch('/api/content/upload', { method: 'POST', body: form });
                const data = await res.json();
                alert('Content uploaded! ID: ' + data.content_id);
            }
            loadMetrics();
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
