"""
Database utilities with connection pooling and error handling
"""
import sqlite3
import logging
from contextlib import contextmanager
from typing import Optional
from config.settings import config

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database operations"""
    pass


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Ensures connections are properly closed.
    """
    conn = None
    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        # Enable foreign key support for cascade deletes
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise DatabaseError(f"Failed to connect to database: {e}") from e
    finally:
        if conn:
            conn.close()


def init_database():
    """
    Initialize database tables.
    Creates all required tables if they don't exist.
    """
    schema = """
        -- Content table: stores uploaded photos/videos with metadata
        CREATE TABLE IF NOT EXISTS content (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            caption TEXT,
            context TEXT,  -- Additional context about the content (recipe, story, etc.)
            hashtags TEXT,  -- JSON array
            scheduled_time TIMESTAMP,
            posted_time TIMESTAMP,
            status TEXT DEFAULT 'pending',  -- pending, scheduled, posted, failed
            engagement_score REAL,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            saves INTEGER DEFAULT 0,
            external_id TEXT,  -- Instagram post ID
            content_type TEXT,   -- breakfast, lunch, dinner, dessert
            cuisine_type TEXT    -- italian, indian, etc.
        );
        
        CREATE INDEX IF NOT EXISTS idx_content_status ON content(status);
        CREATE INDEX IF NOT EXISTS idx_content_scheduled ON content(scheduled_time);
        
        -- Competitors table: tracks competitor accounts
        CREATE TABLE IF NOT EXISTS competitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            follower_count INTEGER DEFAULT 0,
            avg_engagement REAL DEFAULT 0,
            last_analyzed TIMESTAMP,
            top_hashtags TEXT,  -- JSON array
            content_patterns TEXT,  -- JSON array
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Growth metrics table: tracks daily stats
        CREATE TABLE IF NOT EXISTS growth_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            followers INTEGER DEFAULT 0,
            posts INTEGER DEFAULT 0,
            avg_likes REAL DEFAULT 0,
            avg_comments REAL DEFAULT 0,
            avg_saves REAL DEFAULT 0,
            reach INTEGER DEFAULT 0,
            profile_visits INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_growth_date ON growth_metrics(date);
        
        -- Hashtag performance table
        CREATE TABLE IF NOT EXISTS hashtag_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hashtag TEXT UNIQUE NOT NULL,
            category TEXT,
            avg_engagement REAL DEFAULT 0,
            usage_count INTEGER DEFAULT 0,
            last_used TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_hashtag_engagement ON hashtag_performance(avg_engagement DESC);
        
        -- Strategy recommendations table
        CREATE TABLE IF NOT EXISTS strategy_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            content_theme TEXT NOT NULL,
            recommended_hashtags TEXT,  -- JSON
            optimal_times TEXT,  -- JSON
            competitor_insights TEXT,  -- JSON
            growth_actions TEXT,  -- JSON
            applied BOOLEAN DEFAULT 0,
            week_starting DATE
        );
        
        -- Posting log table
        CREATE TABLE IF NOT EXISTS posting_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id TEXT REFERENCES content(id),
            attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN,
            method TEXT,
            error_message TEXT,
            external_post_id TEXT
        );
        
        -- System settings table
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Insert default settings
        INSERT OR IGNORE INTO system_settings (key, value) VALUES 
            ('instagram_connected', 'false'),
            ('last_strategy_update', NULL),
            ('account_created', datetime('now'));
        
        -- Reel Maker tables: separate from content upload flow
        
        -- Reel projects table: stores reel creation projects
        CREATE TABLE IF NOT EXISTS reel_projects (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'draft',  -- draft, queued, analyzing, rendering, ready, failed, published
            template_key TEXT DEFAULT 'dish_showcase',  -- dish_showcase, recipe_steps, ambience_montage, platter_reveal
            target_duration_seconds INTEGER DEFAULT 30,
            caption TEXT,
            hashtags TEXT,  -- JSON array
            final_output_path TEXT,
            final_output_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_reel_projects_status ON reel_projects(status);
        CREATE INDEX IF NOT EXISTS idx_reel_projects_created ON reel_projects(created_at DESC);
        
        -- Reel assets table: stores uploaded images/videos for a reel project
        CREATE TABLE IF NOT EXISTS reel_assets (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES reel_projects(id) ON DELETE CASCADE,
            source_path TEXT NOT NULL,
            media_type TEXT NOT NULL,  -- image, video
            sort_order INTEGER DEFAULT 0,
            analysis_json TEXT,  -- Structured analysis: dish detection, quality scores, visual facts
            selected BOOLEAN DEFAULT 1,  -- Whether planner selected this asset for render
            preview_path TEXT,  -- Browser-safe preview thumbnail
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_reel_assets_project ON reel_assets(project_id);
        CREATE INDEX IF NOT EXISTS idx_reel_assets_selected ON reel_assets(project_id, selected);
        
        -- Reel render jobs table: tracks async video rendering
        CREATE TABLE IF NOT EXISTS reel_render_jobs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES reel_projects(id) ON DELETE CASCADE,
            status TEXT DEFAULT 'queued',  -- queued, analyzing, running, completed, failed
            edit_plan_json TEXT,  -- Validated edit plan consumed by renderer
            error_message TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_reel_render_jobs_project ON reel_render_jobs(project_id);
        CREATE INDEX IF NOT EXISTS idx_reel_render_jobs_status ON reel_render_jobs(status);
        
        -- Reel publish jobs table: tracks Instagram publishing attempts
        CREATE TABLE IF NOT EXISTS reel_publish_jobs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES reel_projects(id) ON DELETE CASCADE,
            status TEXT DEFAULT 'queued',  -- queued, publishing, published, failed
            external_media_id TEXT,  -- Instagram media/container id
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_reel_publish_jobs_project ON reel_publish_jobs(project_id);

        -- Reel recommendations table: caches AI-generated recommendations
        CREATE TABLE IF NOT EXISTS reel_recommendations (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES reel_projects(id) ON DELETE CASCADE,
            recommendation_json TEXT NOT NULL,  -- Full recommendation payload
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_reel_recommendations_project ON reel_recommendations(project_id);

        -- Scheduled reel posts table: tracks reels scheduled for future publishing
        CREATE TABLE IF NOT EXISTS scheduled_reel_posts (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES reel_projects(id) ON DELETE CASCADE,
            caption TEXT,
            hashtags TEXT,  -- JSON array
            scheduled_time TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'pending',  -- pending, published, cancelled, failed
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            published_at TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_scheduled_reel_posts_project ON scheduled_reel_posts(project_id);
        CREATE INDEX IF NOT EXISTS idx_scheduled_reel_posts_time ON scheduled_reel_posts(scheduled_time);
        CREATE INDEX IF NOT EXISTS idx_scheduled_reel_posts_status ON scheduled_reel_posts(status);
    """
    
    try:
        with get_db_connection() as conn:
            conn.executescript(schema)
            conn.commit()
            logger.info("Database initialized successfully")
    except DatabaseError:
        raise
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise DatabaseError(f"Database initialization failed: {e}") from e


def execute_query(query: str, params: tuple = ()) -> list:
    """
    Execute a SELECT query and return results.
    
    Args:
        query: SQL query string
        params: Query parameters (for parameterized queries)
        
    Returns:
        List of Row objects
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Query execution error: {e}, Query: {query}")
        raise DatabaseError(f"Query failed: {e}") from e


def execute_insert(query: str, params: tuple = ()) -> int:
    """
    Execute an INSERT/UPDATE/DELETE query.
    
    Args:
        query: SQL query string
        params: Query parameters
        
    Returns:
        Last row ID for inserts, or row count for updates/deletes
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.lastrowid if cursor.lastrowid else cursor.rowcount
    except sqlite3.Error as e:
        logger.error(f"Insert/Update error: {e}, Query: {query}")
        raise DatabaseError(f"Operation failed: {e}") from e


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a system setting value"""
    try:
        rows = execute_query(
            "SELECT value FROM system_settings WHERE key = ?",
            (key,)
        )
        return rows[0]["value"] if rows else default
    except DatabaseError:
        return default


def set_setting(key: str, value: str) -> bool:
    """Set a system setting value"""
    try:
        execute_insert(
            """
            INSERT INTO system_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value)
        )
        return True
    except DatabaseError:
        return False
