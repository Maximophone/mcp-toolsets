# MCP Toolsets

A modular Model Context Protocol (MCP) server that provides AI tools for filesystem operations, Gmail, Discord, Notion, LinkedIn, and more.

Built with FastAPI, this server exposes multiple toolsets as virtual MCP endpoints, allowing AI applications to selectively use the tools they need.

## Features

- **Virtual MCP Servers**: Single process, multiple toolsets at different URL paths
- **Modular Toolsets**: System, Gmail, Discord, Notion, LinkedIn (each accessible independently)
- **Security**: API key authentication + path sandboxing
- **FastAPI**: Modern async Python framework with auto-generated docs

## Quick Start

### 1. Install Dependencies

```bash
cd mcp-toolsets
pip install -r requirements.txt
```

### 2. Configure

```bash
# Copy the example config
cp .env.example .env

# Edit .env with your settings
nano .env
```

### 3. Run

```bash
python server.py
```

The server starts and exposes each toolset as a virtual MCP server:

```
http://127.0.0.1:8765/mcp/system   → Filesystem/shell tools
http://127.0.0.1:8765/mcp/gmail    → Email tools
http://127.0.0.1:8765/mcp/discord  → Discord tools
http://127.0.0.1:8765/mcp/notion   → Notion database tools
http://127.0.0.1:8765/mcp/linkedin → LinkedIn tools
```

API Docs: http://127.0.0.1:8765/docs

### 4. Connect Your MCP Client

Each toolset is available at its own endpoint:

| Toolset | URL |
|---------|-----|
| System | `http://127.0.0.1:8765/mcp/system` |
| Gmail | `http://127.0.0.1:8765/mcp/gmail` |
| Discord | `http://127.0.0.1:8765/mcp/discord` |
| Notion | `http://127.0.0.1:8765/mcp/notion` |
| LinkedIn | `http://127.0.0.1:8765/mcp/linkedin` |

Configure your MCP client to connect to the toolsets you need. Each toolset exposes:
- `GET /tools` - List available tools
- `POST /execute` - Execute a tool

## Configuration

Environment variables (via `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_API_KEY` | `dev-key-12345` | API key for authentication |
| `MCP_PORT` | `8765` | Port to listen on |
| `MCP_HOST` | `127.0.0.1` | Host to bind to |
| `MCP_BASE_DIR` | `~` (home) | Base directory for filesystem operations |
| `MCP_ENABLED_TOOLSETS` | `system` | Comma-separated list of enabled toolsets |
| `LOG_LEVEL` | `INFO` | Logging level |

## API

All endpoints require authentication via `Authorization: Bearer <api_key>` header.

### List Available Toolsets
```
GET /mcp/toolsets
```

### Per-Toolset Endpoints

Each toolset has its own endpoints:

```
GET  /mcp/{toolset}/health  - Health check
GET  /mcp/{toolset}/tools   - List tools
POST /mcp/{toolset}/execute - Execute a tool
```

Example - list system tools:
```
GET /mcp/system/tools
```

Example - execute a tool:
```
POST /mcp/system/execute
Content-Type: application/json

{
  "name": "list_directory",
  "arguments": {
    "path": "/Users/me/Documents"
  }
}
```

### Legacy Endpoints (All Tools)

For backward compatibility, these endpoints serve all enabled tools:

```
GET  /health  - Health check (all toolsets)
GET  /tools   - List all tools
POST /execute - Execute any tool
```

## Available Toolsets

### System Toolset (`system`)

| Tool | Safe | Description |
|------|------|-------------|
| `list_directory` | ✅ | List files and directories |
| `read_file` | ✅ | Read file contents with line numbers |
| `save_file` | ❌ | Save content to a file |
| `copy_file` | ❌ | Copy or move a file |
| `run_command` | ❌ | Run a shell command |
| `execute_python` | ❌ | Execute Python code |
| `fetch_webpage` | ✅ | Fetch URL and convert to markdown |
| `persistent_shell` | ❌ | Persistent shell session |

### Gmail Toolset (`gmail`)

Requires OAuth credentials. See [Gmail Setup](#gmail-setup) below.

| Tool | Safe | Description |
|------|------|-------------|
| `send_email` | ❌ | Send an email |
| `reply_to_email` | ❌ | Reply to an email in thread |
| `search_emails` | ✅ | Search emails with filters |
| `get_email_content` | ✅ | Get full email content |
| `list_recent_emails` | ✅ | List recent emails |
| `list_email_attachments` | ✅ | List email attachments |
| `download_email_attachments` | ❌ | Download attachments |

#### Gmail Setup

1. **Create Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project (or select existing)

2. **Enable Gmail API**
   - Go to APIs & Services → Library
   - Search for "Gmail API" and enable it

3. **Create OAuth Credentials**
   - Go to APIs & Services → Credentials
   - Click "Create Credentials" → "OAuth client ID"
   - Select "Desktop app" as application type
   - Download the JSON file

4. **Configure MCP Server**
   ```bash
   # Save credentials in project directory
   mv ~/Downloads/client_secret_xxx.json credentials.json
   
   # Enable gmail toolset in .env
   MCP_ENABLED_TOOLSETS=system,gmail
   ```

5. **First Run - OAuth Flow**
   - Start the server and call any Gmail tool
   - A browser window will open for Google sign-in
   - Grant permissions to your app
   - `token.pickle` will be saved for future use

### Discord Toolset (`discord`)

Requires a Discord bot token. See [Discord Setup](#discord-setup) below.

| Tool | Safe | Description |
|------|------|-------------|
| `list_discord_channels` | ✅ | List accessible channels |
| `read_discord_messages` | ✅ | Read channel messages |
| `send_discord_dm` | ❌ | Send a direct message |
| `read_discord_dm_history` | ✅ | Read DM history |
| `send_discord_message` | ❌ | Send message to channel |
| `get_discord_user` | ✅ | Get user information |

#### Discord Setup

1. **Create Discord Application**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application" and name it

2. **Create Bot**
   - Go to "Bot" section in your application
   - Click "Add Bot"
   - Under "Privileged Gateway Intents", enable:
     - Message Content Intent
     - Server Members Intent

3. **Get Bot Token**
   - In the Bot section, click "Reset Token" to get your token
   - Copy the token (you can only see it once!)

4. **Invite Bot to Server**
   - Go to "OAuth2" → "URL Generator"
   - Select scopes: `bot`
   - Select permissions: `Read Messages/View Channels`, `Send Messages`, `Read Message History`
   - Copy the generated URL and open it in browser
   - Select your server and authorize

5. **Configure MCP Server**
   ```bash
   # Add to .env
   DISCORD_BOT_TOKEN=your-bot-token-here
   MCP_ENABLED_TOOLSETS=system,discord
   ```

### Notion Toolset (`notion`)

Tools for interacting with Notion databases - read schemas, query rows, create/update entries.

| Tool | Safe | Description |
|------|------|-------------|
| `list_databases` | ✅ | List all databases shared with integration |
| `get_database_schema` | ✅ | Get database structure and properties |
| `query_database` | ✅ | Query rows from a database |
| `query_database_filtered` | ✅ | Query with Notion filter syntax |
| `get_database_row` | ✅ | Get a specific row by ID |
| `create_database_row` | ❌ | Create a new row in database |
| `update_database_row` | ❌ | Update row properties (requires row_name for review) |
| `update_database_rows` | ❌ | Update multiple rows at once (bulk edit) |
| `archive_database_row` | ❌ | Archive (soft-delete) a row (requires row_name for review) |
| `unarchive_database_row` | ❌ | Restore an archived row (requires row_name for review) |
| `search_notion` | ✅ | Search databases and pages |

#### Notion Setup

1. **Create a Notion Integration**
   - Go to [My Integrations](https://www.notion.so/my-integrations)
   - Click "New integration"
   - Name it (e.g., "MCP Server")
   - Select the workspace to connect
   - Click "Submit"

2. **Get the Integration Token**
   - On the integration page, find "Internal Integration Token"
   - Click "Show" and copy the token (starts with `secret_`)

3. **Share Databases with the Integration**
   - Open each Notion database you want to access
   - Click "..." → "Add connections"
   - Select your integration
   - This grants the integration access to that database

4. **Configure MCP Server**
   ```bash
   # Add to .env
   NOTION_API_KEY=secret_xxxxxxxxxxxxxxxxxxxxxxx
   MCP_ENABLED_TOOLSETS=system,notion
   ```

5. **Test the Tools**
   ```bash
   # List databases
   curl -X POST http://127.0.0.1:8765/mcp/notion/execute \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"name": "list_databases", "arguments": {}}'
   ```

### LinkedIn Toolset (`linkedin`)

Tools for interacting with LinkedIn - profile lookups, people search, messaging, and batch data retrieval.

> ⚠️ **Important**: This uses an **unofficial API** that reverse-engineers LinkedIn's internal Voyager API. Conservative rate limits are enforced to avoid account restrictions. Use responsibly.

| Tool | Safe | Description |
|------|------|-------------|
| `get_linkedin_profile` | ✅ | Get profile by public ID or URN |
| `get_my_linkedin_profile` | ✅ | Get your own profile |
| `get_linkedin_contact_info` | ✅ | Get contact info (if shared) |
| `search_linkedin_people` | ✅ | Search for people with filters |
| `get_my_linkedin_connections` | ✅ | List your 1st-degree connections |
| `list_linkedin_conversations` | ✅ | List message threads |
| `get_linkedin_conversation` | ✅ | Read messages in a conversation |
| `send_linkedin_message` | ❌ | Send a direct message |
| `reply_to_linkedin_conversation` | ❌ | Reply to existing thread |
| `batch_get_linkedin_profiles` | ❌ | Fetch multiple profiles (max 20) |
| `get_linkedin_rate_limit_status` | ✅ | Check remaining daily limits |

**Rate Limits (conservative defaults):**
| Operation | Delay | Daily Limit |
|-----------|-------|-------------|
| Profile lookups | 10-30s | 500/day |
| Searches | 30-60s | 100/day |
| Messages | 60-180s | 100/day |

#### LinkedIn Setup

LinkedIn authentication can be done in 3 ways (in order of preference):

##### Option 1: Browser Cookies (Recommended - Automatic)

If you're logged into LinkedIn in Brave, Chrome, Firefox, or Edge, the server will automatically extract your session cookies. Just make sure:
- You're logged into LinkedIn in your browser
- The browser is running (or cookies are accessible)
- You're running Python as the same user who logged into the browser

##### Option 2: Manual Cookie Extraction

If automatic cookie extraction doesn't work, you can manually copy the cookies:

1. **Open LinkedIn in your browser** and make sure you're logged in

2. **Open Developer Tools**
   - Chrome/Edge/Brave: Press `F12` or `Ctrl+Shift+I` (Windows) / `Cmd+Option+I` (Mac)
   - Firefox: Press `F12` or `Ctrl+Shift+I` (Windows) / `Cmd+Option+I` (Mac)

3. **Navigate to Cookies**
   - Chrome/Edge/Brave: Go to **Application** tab → **Storage** → **Cookies** → `https://www.linkedin.com`
   - Firefox: Go to **Storage** tab → **Cookies** → `https://www.linkedin.com`

4. **Find and copy these two cookies:**

   | Cookie Name | What to Copy |
   |-------------|--------------|
   | `li_at` | The full value (a long string starting with `AQ...`) |
   | `JSESSIONID` | The full value (in quotes, like `"ajax:123456789"`) |

   > 💡 **Tip**: Double-click the value field to select it, then copy. Make sure to get the complete value.

5. **Add to your `.env` file:**
   ```bash
   LINKEDIN_LI_AT=AQEDAQxxxxxxxxxxxxxx...
   LINKEDIN_JSESSIONID='"ajax:1234567890123456789"'
   ```

   > ⚠️ **Important JSESSIONID format**: The value must include the double quotes as part of the value. Use single quotes around the whole thing in .env to preserve them: `LINKEDIN_JSESSIONID='"ajax:..."'`

##### Option 3: Username/Password

You can also authenticate with your LinkedIn credentials, but this may fail if LinkedIn requires 2FA or shows a CAPTCHA:

```bash
# Add to .env
LINKEDIN_EMAIL=your-email@example.com
LINKEDIN_PASSWORD=your-password
```

#### Enable LinkedIn Toolset

```bash
# Add to .env
MCP_ENABLED_TOOLSETS=system,linkedin
```

#### Test Authentication

Run the test script to verify your LinkedIn setup:

```bash
python test_linkedin_auth.py
```

This will check:
- Environment variables
- Browser cookie availability
- Actual API connection
- Your profile information

#### Troubleshooting

**"LinkedIn authentication failed"**
- Make sure you're logged into LinkedIn in your browser
- Try closing all browser windows and re-logging into LinkedIn
- Use Option 2 (manual cookies) if automatic extraction fails
- Check that your cookies haven't expired (they typically last several weeks)

**"CHALLENGE" or 2FA errors with username/password**
- LinkedIn may require verification for new logins
- Use cookie-based authentication instead (Option 1 or 2)

**Rate limit errors**
- The toolset enforces conservative daily limits
- Use `get_linkedin_rate_limit_status` to check remaining quota
- Limits reset at midnight

## Security

1. **API Key Authentication**: All requests must include valid API key
2. **Path Sandboxing**: All filesystem operations are restricted to `MCP_BASE_DIR`
3. **Safe Flag**: Tools marked `safe=False` require user confirmation in the plugin

## Development

### Adding a New Toolset

1. Create `toolsets/my_toolset.py`:

```python
from .base import tool, RegisteredTool

@tool(
    description="My awesome tool",
    param1="Description of param1",
    safe=True
)
def my_tool(param1: str) -> str:
    return f"Result: {param1}"

TOOLS = [my_tool]
```

2. Register in `toolsets/__init__.py`:

```python
from . import my_toolset
register_toolset("my_toolset", my_toolset.TOOLS)
```

3. Enable in `.env`:

```
MCP_ENABLED_TOOLSETS=system,my_toolset
```

### Running in Development

```bash
uvicorn server:app --reload --host 127.0.0.1 --port 8765
```

## Project Structure

```
mcp-toolsets/
├── server.py              # FastAPI main server
├── config.py              # Configuration loading
├── requirements.txt       # Python dependencies
├── test_linkedin_auth.py  # LinkedIn auth test script
├── .env.example        # Environment template
├── .env                # Your local config (gitignored)
├── credentials.json    # Gmail OAuth credentials (gitignored)
├── token.pickle        # Gmail OAuth token (gitignored)
├── data/               # Runtime data (gitignored)
│   └── rate_limits/    # LinkedIn rate limit state
├── toolsets/
│   ├── __init__.py     # Toolset registry
│   ├── base.py         # @tool decorator
│   ├── system.py       # Filesystem/shell tools
│   ├── gmail.py        # Gmail tools
│   ├── discord.py      # Discord tools
│   ├── notion.py       # Notion database tools
│   └── linkedin.py     # LinkedIn tools
├── integrations/
│   ├── __init__.py
│   ├── gmail_client.py    # Gmail API client
│   ├── discord_client.py  # Discord bot client
│   ├── notion_client.py   # Notion API client
│   └── linkedin_client.py # LinkedIn API client
└── utils/
    ├── __init__.py
    └── rate_limiter.py    # Rate limiting utilities
```

## Compatible Clients

This MCP server works with any client that supports the Model Context Protocol:

- **[Obsidian AI Plugin](https://github.com/Maximophone/obsidian-ai-plugin)** - AI-powered note processing for Obsidian
- Any other MCP-compatible AI client

## License

MIT
