# Instagram Profile Configuration Guide

This guide explains how to configure your Instagram profile with the Hungry Panda agent.

## Table of Contents
1. [Quick Setup](#quick-setup)
2. [Configuration Methods](#configuration-methods)
3. [Account Types Explained](#account-types-explained)
4. [Posting Methods](#posting-methods)
5. [Testing Your Setup](#testing-your-setup)
6. [Troubleshooting](#troubleshooting)

---

## Quick Setup

### Step 1: Copy the Example Config

```bash
cd hungry-panda
cp config/.env.example config/.env
```

### Step 2: Edit the Configuration

Open `config/.env` and set your Instagram username:

```env
# Required - Your Instagram handle (without @)
INSTAGRAM_USERNAME=your_wifes_username

# Account type (personal, business, creator)
INSTAGRAM_ACCOUNT_TYPE=personal

# How posts are published (manual recommended for now)
POSTING_METHOD=manual

# Optional - for enhanced AI captions
OPENAI_API_KEY=your_key_here
```

### Step 3: Start the Agent

```bash
cd backend
python main.py
```

### Step 4: Access the Dashboard

Open `http://localhost:8000` in your browser.

---

## Configuration Methods

### Method 1: Manual Mode (Recommended)

**Best for:** Personal accounts, authenticity, safety

The agent prepares optimized content and tells you exactly when and what to post. You maintain full control.

**Setup:**
```env
INSTAGRAM_USERNAME=your_username
POSTING_METHOD=manual
```

**How it works:**
1. You upload a food photo to the dashboard
2. AI analyzes and suggests caption, hashtags, best time
3. You approve or edit the suggestions
4. At the optimal time, agent shows you exactly what to post
5. You open Instagram app and post manually
6. Agent tracks the performance

**Benefits:**
- ✅ No risk of account bans
- ✅ Maintains authentic engagement
- ✅ No API keys needed
- ✅ Works with any account type

### Method 2: Instagram Graph API (Business/Creator)

**Best for:** Business accounts, high-volume posting, automation

Uses Instagram's official API. Requires Business or Creator account.

**Setup:**
1. Convert Instagram to Business or Creator account
2. Connect to Facebook Business account
3. Create Facebook App and get credentials
4. Configure:
```env
INSTAGRAM_ACCOUNT_TYPE=business
POSTING_METHOD=api
INSTAGRAM_APP_ID=your_app_id
INSTAGRAM_APP_SECRET=your_app_secret
INSTAGRAM_ACCESS_TOKEN=your_token
```

**Note:** Instagram Basic Display API has limitations (read-only for personal accounts). For posting, you need:
- Instagram Business Account
- Connected Facebook Page
- Facebook App with oEmbed product
- `instagram_basic` and `pages_read_engagement` permissions

**Benefits:**
- ✅ Fully automated posting
- ✅ Official API (safe)
- ✅ Rich analytics

**Drawbacks:**
- ❌ Requires Business/Creator account
- ❌ Complex setup
- ❌ Some features limited

### Method 3: Browser Automation (Advanced)

**Best for:** Personal accounts that need automation

Uses browser automation to mimic human posting. More fragile than official API.

**Setup:**
```env
INSTAGRAM_USERNAME=your_username
INSTAGRAM_PASSWORD=your_password
POSTING_METHOD=browser
```

**Warning:** This method requires careful setup to avoid detection:
- Proper delays between actions
- Anti-detection measures
- Proxy rotation (for multiple accounts)
- Risk of temporary blocks

**Benefits:**
- ✅ Works with personal accounts
- ✅ Full feature support
- ✅ Can post stories, reels

**Drawbacks:**
- ❌ Higher ban risk
- ❌ Requires maintenance
- ❌ May break with Instagram UI changes

---

## Account Types Explained

### Personal Account
- Standard Instagram account
- Best for: Individual creators, small food blogs
- Limitations: Cannot use Graph API for posting
- **Recommendation:** Use with `POSTING_METHOD=manual`

### Business Account
- Designed for businesses
- Access to: Insights, ads, shopping, contact button
- Can use: Graph API for posting
- **Recommendation:** Best for serious growth, enables API posting

### Creator Account
- Designed for influencers
- Access to: Growth insights, branded content tools
- Can use: Graph API for posting
- **Recommendation:** Good balance of features

### How to Switch Account Type

1. Open Instagram app
2. Go to Settings → Account → Switch Account Type
3. Select Business or Creator
4. Follow setup prompts
5. If Business: Connect Facebook Page (required)

---

## Posting Methods Comparison

| Method | Account Type | Automation | Risk | Setup Complexity |
|--------|--------------|------------|------|------------------|
| **Manual** | Any | None | None | Easy |
| **API** | Business/Creator | Full | Low | Complex |
| **Browser** | Any | Full | Medium-High | Complex |

### Our Recommendation

**Start with Manual mode.** Here's why:
1. Instagram's algorithm favors authentic engagement
2. No risk to the account
3. You can always upgrade to automation later
4. The agent still does 90% of the work (analysis, curation, scheduling)

---

## Testing Your Setup

### 1. Check Configuration

Visit: `http://localhost:8000/api/config/profile`

Should show:
```json
{
  "username": "your_username",
  "account_type": "personal",
  "posting_method": "manual",
  "configured": true
}
```

### 2. Health Check

Visit: `http://localhost:8000/api/health`

Should show:
```json
{
  "status": "healthy",
  "config_valid": true,
  "analyzer_available": true
}
```

### 3. Test Upload

1. Open dashboard at `http://localhost:8000`
2. Click "Upload Content"
3. Select a food photo
4. Check that AI recommendations appear

### 4. Add a Competitor

In the dashboard:
1. Scroll to "Competitor Insights"
2. Enter a food Instagram account (e.g., `halfbakedharvest`)
3. Click "Track Competitor"
4. Verify it appears in the list

---

## Troubleshooting

### "Configuration not valid" error

**Problem:** `INSTAGRAM_USERNAME` not set

**Fix:**
```bash
# Edit config/.env
INSTAGRAM_USERNAME=your_actual_username
```

### "Analyzer not available" error

**Problem:** Python import errors

**Fix:**
```bash
cd hungry-panda
pip install -r requirements.txt
cd backend
python main.py
```

### Dashboard not loading

**Problem:** Frontend file not found

**Fix:**
Check that `frontend/dashboard.html` exists. If using fallback dashboard, you'll see a simple message with a link to API docs.

### Cannot add competitor

**Problem:** Competitor tracking disabled or error

**Fix:**
```env
# In config/.env
ENABLE_COMPETITOR_TRACKING=true
```

Then restart the server.

### Want to use OpenAI for better captions?

**Setup:**
1. Get API key from [OpenAI](https://platform.openai.com)
2. Add to config:
```env
OPENAI_API_KEY=sk-your-key-here
```
3. Restart agent

Without OpenAI, the agent uses built-in templates (still effective).

---

## Security Best Practices

1. **Never commit `.env` file**
   - It's already in `.gitignore`
   - Contains sensitive credentials

2. **Use strong Instagram password**
   - If using browser automation method
   - Consider app-specific password

3. **Rotate API keys regularly**
   - OpenAI keys
   - Instagram tokens

4. **Backup your database**
   - `hungry_panda.db` contains all data
   - Copy it periodically

---

## Next Steps

1. ✅ Configure your profile (config/.env)
2. ✅ Start the agent (`python main.py`)
3. ✅ Test with a food photo upload
4. ✅ Add 3-5 competitor accounts to track
5. ✅ Generate your first weekly strategy
6. ✅ Post consistently using agent recommendations

---

## Support

If issues persist:
1. Check logs in `logs/hungry_panda.log`
2. Verify all requirements installed
3. Try the health check endpoint
4. Review this guide for your specific setup
