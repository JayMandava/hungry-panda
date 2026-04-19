# Step 2 Checklist - Track Your Progress

Print this out or copy it to track your Instagram API setup progress.

## Part 1: Instagram Business Account ☐

- [ ] Opened Instagram app
- [ ] Navigated to Settings → Account → Switch account type
- [ ] Selected "Switch to Professional Account"
- [ ] Chose "Business" (not Creator)
- [ ] Selected category (Food & Drink)
- [ ] Completed the setup wizard
- [ ] **VERIFIED:** Profile now shows "Business" badge

## Part 2: Facebook Page Connection ☐

- [ ] Went to Settings → Linked Accounts → Facebook
- [ ] Connected existing page OR created new page
- [ ] Page name: _______________________________
- [ ] **VERIFIED:** Can see the page in Facebook

## Part 3: Facebook App Creation ☐

- [ ] Visited developers.facebook.com
- [ ] Logged in with same Facebook account
- [ ] Clicked "My Apps" → "Create App"
- [ ] Selected "Business" app type
- [ ] Named app: "Hungry Panda - Instagram Agent"
- [ ] Created app successfully
- [ ] Added "Instagram Basic Display" product
- [ ] Added "Instagram Graph API" product
- [ ] **VERIFIED:** App appears in dashboard

## Part 4: Getting Credentials ☐

### App Credentials
- [ ] Went to Settings → Basic
- [ ] Copied App ID: _______________________________
- [ ] Clicked "Show" on App Secret
- [ ] Copied App Secret: _______________________________

### Instagram Business Account ID
- [ ] Opened Graph API Explorer
- [ ] Selected my app
- [ ] Generated token with permissions:
  - [ ] instagram_basic
  - [ ] instagram_content_publish
  - [ ] pages_show_list
  - [ ] pages_read_engagement
- [ ] Made request to `me/accounts`
- [ ] Found Facebook Page → clicked its ID
- [ ] Found `instagram_business_account` field
- [ ] Copied the ID: _______________________________

### Long-Lived Access Token
- [ ] Used the short token from Graph API Explorer
- [ ] Made GET request to convert to long-lived:
```
https://graph.facebook.com/v19.0/oauth/access_token?
  grant_type=fb_exchange_token&
  client_id=___&
  client_secret=___&
  fb_exchange_token=___
```
- [ ] Received response with access_token
- [ ] Copied Long-Lived Token: _______________________________

## Part 5: Hungry Panda Configuration ☐

- [ ] Ran `python scripts/setup_mcp.py`
- [ ] OR manually edited `config/.env`
- [ ] Filled in all 5 credentials:
  - [ ] INSTAGRAM_USERNAME
  - [ ] INSTAGRAM_APP_ID
  - [ ] INSTAGRAM_APP_SECRET
  - [ ] INSTAGRAM_ACCESS_TOKEN
  - [ ] INSTAGRAM_BUSINESS_ACCOUNT_ID
- [ ] Set ENABLE_MCP_INTEGRATION=true
- [ ] Set POSTING_METHOD=mcp
- [ ] Saved the file

## Part 6: Install ig-mcp Server ☐

- [ ] Ran: `git clone https://github.com/jlbadano/ig-mcp.git`
- [ ] Ran: `cd ig-mcp && pip install -r requirements.txt`
- [ ] Updated MCP_SERVER_PATH in .env

## Part 7: Testing ☐

- [ ] Started Hungry Panda: `cd backend && python main.py`
- [ ] Opened http://localhost:8000/api/health
- [ ] **VERIFIED:** Shows "config_valid": true
- [ ] Opened main dashboard
- [ ] Uploaded a test photo
- [ ] Scheduled it for posting
- [ ] **VERIFIED:** Content posted to Instagram automatically

## Credentials Summary

Keep this safe! You'll need these for any future setup.

| Credential | Value |
|------------|-------|
| Instagram Username | @_________________ |
| App ID | _________________________ |
| App Secret | _________________________ |
| Access Token | EAABs... (first 10 chars: _______) |
| Business Account ID | _________________________ |

## Support

If stuck on any step:
1. Check [STEP2_WALKTHROUGH.md](STEP2_WALKTHROUGH.md) for detailed instructions
2. Check [MCP_INTEGRATION.md](MCP_INTEGRATION.md) for troubleshooting
3. Visit https://github.com/jlbadano/ig-mcp for server-specific issues
4. Check Facebook Developer documentation: developers.facebook.com/docs/instagram-api/

---

**Date Started:** ___________  
**Date Completed:** ___________  
**Ready to automate Instagram posting:** ☐
