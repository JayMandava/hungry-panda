# Project Context Database

## Overview

The `project-context.db` SQLite database tracks everything built for Hungry Panda. It serves as a reference for:
- What features were built
- When they were built (git commits)
- What issues were fixed
- API endpoints available
- Configuration details

## Database Schema

### Tables

1. **features** - All modules/features built
   - id, name, description, status, category, file_path, notes

2. **commits** - Git commit history
   - hash, message, date, files_changed, insertions, deletions

3. **issues** - Problems encountered and solutions
   - title, description, status, solution, affected_files

4. **config** - Key configuration values
   - key, value, description, category

5. **endpoints** - API endpoints
   - path, method, description, parameters

6. **schema_versions** - Database migrations

## Quick Queries

```bash
# View all features
sqlite3 project-context.db "SELECT name, category FROM features;"

# View recent commits
sqlite3 project-context.db "SELECT hash, message FROM commits ORDER BY date DESC LIMIT 5;"

# View issues fixed
sqlite3 project-context.db "SELECT title, solution FROM issues;"

# View config
sqlite3 project-context.db "SELECT key, value FROM config;"

# View endpoints
sqlite3 project-context.db "SELECT path, method FROM endpoints;"
```

## Current Stats

- **Features Built:** 12
- **Git Commits:** 19
- **Issues Fixed:** 5
- **API Endpoints:** 12

## Network URLs (from config)

- WiFi: http://192.168.0.204:8080
- Tailscale: http://100.102.200.54:8080 or http://100.96.0.26:8080

## AI Configuration (from config)

- Provider: Fireworks AI
- Model: accounts/fireworks/models/kimi-k2p5
- API URL: https://api.fireworks.ai/inference/v1
