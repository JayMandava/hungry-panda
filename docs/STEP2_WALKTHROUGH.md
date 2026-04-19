# STEP 2: Instagram API Credentials - Detailed Walkthrough

This guide walks you through getting Instagram API credentials for Hungry Panda MCP integration.

**Time required:** 15-20 minutes  
**Difficulty:** Medium  
**What you need:** Instagram app, Facebook account, patience

---

## Part 1: Convert Instagram to Business Account (5 min)

### Step 1.1: Open Instagram App
1. Open Instagram on your phone
2. Go to your profile (bottom right icon)
3. Tap the hamburger menu (☰) → **Settings**

### Step 1.2: Switch to Professional Account
1. Tap **Account** → **Switch account type**
2. Select **Switch to Professional Account**
3. Choose **Business** (not Creator for now - you can change later)
4. Select a category: **Food & Drink** or **Chef**
5. Complete the setup

**What changed:**
- You now have access to Instagram Insights
- You can connect to Facebook Business tools
- You can use the official Instagram API

---

## Part 2: Connect to Facebook Page (3 min)

### Step 2.1: Link Facebook Page
1. In Instagram, go to **Settings** → **Account** → **Linked Accounts**
2. Tap **Facebook**
3. Either:
   - **Connect existing page** (if you have one)
   - **Create new page** (recommended for simplicity)

### Step 2.2: If Creating New Page
1. Tap **Create New Facebook Page**
2. Page name: `[Your Name] Food Blog` or similar
3. Category: **Food & Drink**
4. Complete setup

**Important:** The Facebook Page must be owned by you and connected to your Instagram Business account.

---

## Part 3: Create Facebook App (5 min)

### Step 3.1: Go to Facebook Developers
1. Open browser → [developers.facebook.com](https://developers.facebook.com)
2. Log in with the **same Facebook account** connected to your Instagram
3. Click **My Apps** (top right) → **Create App**

### Step 3.2: Configure App
1. Select app type: **Business**
2. Click **Next**
3. Fill in details:
   - **App Name:** `Hungry Panda - Instagram Agent`
   - **App Contact Email:** your email
   - **Business Account:** (if shown, select yours)
4. Click **Create App**

### Step 3.3: Add Instagram Products
1. In your app dashboard, scroll to **Add Products**
2. Find **Instagram Basic Display** → Click **Set Up**
3. Click **Create New App** in the Instagram App section
4. Accept terms and create

Then also add:
1. Click **Add Product** again
2. Find **Instagram Graph API** → Click **Set Up**

---

## Part 4: Get Your Credentials (5 min)

### Step 4.1: Get App ID and Secret
1. In your Facebook app dashboard → **Settings** → **Basic**
2. You will see:
   - **App ID:** (long number) - COPY THIS
   - **App Secret:** Click **Show** - COPY THIS

**Save these somewhere safe!**

### Step 4.2: Get Instagram Business Account ID
1. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your app from dropdown
3. Get access token with permissions:
   - Click **Generate Access Token**
   - Select permissions:
     - `instagram_basic`
     - `instagram_content_publish`
     - `pages_show_list`
     - `pages_read_engagement`
4. In the query box, enter: `me/accounts`
5. Click **Submit**
6. Find your Facebook Page → Click on its ID
7. In the response, look for `instagram_business_account`
8. The `id` field is your **Instagram Business Account ID** - COPY THIS

### Step 4.3: Generate Long-Lived Access Token
1. In the Graph API Explorer, get a short token first (as above)
2. Then make this request to convert to long-lived:

**Method:** GET  
**URL:**
```
https://graph.facebook.com/v19.0/oauth/access_token?
  grant_type=fb_exchange_token&
  client_id=YOUR_APP_ID&
  client_secret=YOUR_APP_SECRET&
  fb_exchange_token=YOUR_SHORT_LIVED_TOKEN
```

Replace:
- `YOUR_APP_ID` with your App ID
- `YOUR_APP_SECRET` with your App Secret  
- `YOUR_SHORT_LIVED_TOKEN` with the token from Graph API Explorer

3. The response will contain `access_token` - this is your **Long-Lived Access Token** (valid 60 days) - COPY THIS

---

## Part 5: Configure Hungry Panda (2 min)

### Option A: Run Setup Helper Script
```bash
cd /tmp/hungry-panda
python scripts/setup_mcp.py
```
Enter your credentials when prompted.

### Option B: Manual Configuration
Edit `config/.env`:

```env
# Your Instagram
INSTAGRAM_USERNAME=your_username_here
INSTAGRAM_ACCOUNT_TYPE=business

# API Credentials (from Step 4)
INSTAGRAM_APP_ID=1234567890
INSTAGRAM_APP_SECRET=abc123xyz456
INSTAGRAM_ACCESS_TOKEN=EAABs... (long token)
INSTAGRAM_BUSINESS_ACCOUNT_ID=17841401234567890

# Enable MCP
ENABLE_MCP_INTEGRATION=true
MCP_SERVER_TYPE=ig-mcp
POSTING_METHOD=mcp

# Optional: Path to ig-mcp (install separately)
MCP_SERVER_PATH=/path/to/ig-mcp/src/instagram_mcp_server.py
```

---

## Verification Checklist

- [ ] Instagram is now a Business account
- [ ] Instagram is connected to Facebook Page
- [ ] Facebook App created with Instagram products
- [ ] App ID saved
- [ ] App Secret saved
- [ ] Instagram Business Account ID obtained
- [ ] Long-lived Access Token generated
- [ ] Hungry Panda config updated

---

## Testing Your Setup

1. **Install ig-mcp server:**
```bash
git clone https://github.com/jlbadano/ig-mcp.git ~/ig-mcp
cd ~/ig-mcp
pip install -r requirements.txt
```

2. **Update config with MCP path:**
```env
MCP_SERVER_PATH=/home/YOUR_USERNAME/ig-mcp/src/instagram_mcp_server.py
```

3. **Start Hungry Panda:**
```bash
cd /tmp/hungry-panda/backend
python main.py
```

4. **Check health endpoint:**
Visit: http://localhost:8000/api/health

Should show:
```json
{
  "status": "healthy",
  "config_valid": true,
  "analyzer_available": true
}
```

---

## Troubleshooting

### "Account not found"
- Make sure Instagram is actually connected to Facebook Page
- Check in Instagram: Settings → Account → Linked Accounts → Facebook

### "Invalid access token"
- Token may have expired
- Re-generate in Graph API Explorer
- Make sure you generated a LONG-LIVED token (60 days), not short-lived (1 hour)

### "Insufficient permissions"
- In Facebook App → Instagram Graph API → Permissions
- Make sure you requested: `instagram_basic`, `instagram_content_publish`
- Your app may need to be in "Live" mode (not Development)

### "This action is not allowed"
- Your app needs to be submitted for App Review (for some features)
- For basic posting, Development mode should work

---

## Next Steps

Once Step 2 is complete:
1. Run `python scripts/setup_mcp.py` to save credentials
2. Install ig-mcp server
3. Start Hungry Panda
4. Test uploading and posting content

**Need help?** Refer to:
- [MCP_INTEGRATION.md](MCP_INTEGRATION.md) - Full MCP guide
- [ig-mcp repository](https://github.com/jlbadano/ig-mcp) - Server setup
- [Facebook Graph API docs](https://developers.facebook.com/docs/instagram-api/)
