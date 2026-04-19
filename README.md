# 🐼 Hungry Panda

**AI-Powered Instagram Growth Agent for Food & Cooking**

Hungry Panda is an intelligent Instagram management system that analyzes, strategizes, and executes content to grow a food/cooking Instagram account from its current state to a highly engaging profile.

## Features

### 🤖 AI-Powered Content Curation
- Upload photos/videos and get instant AI analysis
- Auto-generated captions optimized for engagement
- Smart hashtag selection based on trending food content
- Optimal posting time recommendations

### 📊 Growth Dashboard
- Real-time follower growth tracking
- Engagement rate monitoring
- Content performance analytics
- Visual content queue management

### 🎯 Strategic Planning
- Weekly content themes based on analysis
- Competitor tracking and insights
- Market trend identification
- Growth action recommendations

### 📅 Scheduling & Posting
- Smart content scheduling
- Automated posting (with manual fallback)
- Queue management
- Engagement tracking

## Quick Start

### 1. Installation

```bash
git clone <your-repo-url>
cd hungry-panda
pip install -r requirements.txt
```

### 2. Configuration

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Edit `.env` with your settings:
- Instagram credentials (for API or browser automation)
- OpenAI API key (optional, for enhanced captions)
- Other preferences

### 3. Run the Application

```bash
cd backend
python main.py
```

The dashboard will be available at `http://localhost:8000`

## How It Works

### The Growth Loop

1. **Analyze** → Track competitor food accounts, identify trending content patterns, measure hashtag performance
2. **Learn** → Identify what works (e.g., "overhead recipe videos get 3x saves")
3. **Recommend** → Suggest content that matches winning patterns
4. **Curate** → When you upload photos, AI suggests captions, hashtags, and optimal times
5. **Execute** → Schedule and post at best times with optimized copy
6. **Measure** → Track results, refine next recommendations

### Content Flow

```
You Upload Photo → AI Analyzes → Gets Recommendations → 
Approves/Edits → Scheduled → Posted → Metrics Tracked → 
Next Recommendation Improved
```

## Architecture

```
hungry-panda/
├── backend/
│   └── main.py              # FastAPI server & routes
├── analyzer/
│   ├── content_engine.py    # AI caption/hashtag generation
│   ├── competitor_tracker.py # Competitor analysis
│   └── strategist.py        # Weekly strategy generation
├── scheduler/
│   └── poster.py            # Scheduling & posting logic
├── frontend/
│   └── dashboard.html       # Web dashboard UI
├── config/
│   └── .env.example         # Configuration template
└── requirements.txt         # Python dependencies
```

## Key Concepts

### Content Patterns
The agent tracks which content types perform best:
- Overhead recipe videos → 3x saves
- ASMR cooking sounds → 2.5x shares  
- Before/after transformations → 2x comments
- Quick 30-sec tutorials → 4x saves
- Beautiful plating shots → 1.8x likes

### Weekly Themes
Rotating content themes keep the feed fresh:
- Comfort Food Week (high saves)
- Quick & Easy Week (high shares)
- Global Flavors Week (high reach)
- Meal Prep Week (high saves)
- Weekend Special Week (high likes)

### Optimal Posting Times
Based on food content analysis:
- Breakfast: 8:00 AM
- Lunch: 12:00 PM
- Dinner: 6:00 PM (weekdays), 5:00 PM (weekends)
- Dessert: 3:00 PM

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard UI |
| `/api/content/upload` | POST | Upload new content |
| `/api/content/pending` | GET | Get pending content queue |
| `/api/content/{id}/schedule` | POST | Schedule content |
| `/api/growth/dashboard` | GET | Get dashboard metrics |
| `/api/competitors` | GET | List tracked competitors |
| `/api/competitors/add` | POST | Add competitor to track |
| `/api/strategy/generate` | POST | Generate new strategy |

## Instagram Integration

### Current: Manual Mode (Recommended)
The agent prepares optimized content and notifies you when it's time to post. You maintain full control and authenticity.

### Future Options:
1. **Instagram Graph API** - For Business/Creator accounts
2. **Browser Automation** - Selenium/Playwright (requires careful setup)

## Customization

### Adding Caption Templates
Edit `analyzer/content_engine.py`:
```python
CAPTION_TEMPLATES = {
    "your_category": [
        "Your template with {variable} placeholders"
    ]
}
```

### Adding Competitors
Track competitors via the dashboard or API:
```bash
curl -X POST http://localhost:8000/api/competitors/add \
  -H "Content-Type: application/json" \
  -d '{"username": "foodaccount"}'
```

### Custom Hashtags
Modify hashtag categories in `analyzer/content_engine.py` to match your niche.

## Roadmap

- [ ] Instagram Graph API integration
- [ ] Advanced image analysis (detect dish type automatically)
- [ ] Story and Reels automation
- [ ] Comment/DM auto-responses
- [ ] Advanced analytics with charts
- [ ] Multi-account support
- [ ] Mobile app companion

## Notes

- This is designed for food/cooking content but can be adapted
- SQLite database stores all data locally
- AI features work without API keys using built-in templates
- Add OpenAI API key for enhanced caption generation

## License

MIT License - Build freely, grow organically.
