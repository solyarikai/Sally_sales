# New User Flow — First Connection to MCP

## Via Claude Desktop

### Step 1: Add MCP server
Open `~/Library/Application Support/Claude/claude_desktop_config.json` and add:
```json
{
  "mcpServers": {
    "leadgen": {
      "url": "http://46.62.210.24:8002/mcp/sse"
    }
  }
}
```
Restart Claude Desktop.

### Step 2: First message
User: "Hello" or "I want to set up my account"

Claude sees 26 tools available. It calls `setup_account`:
```
Claude: I'll create your account. What's your email and name?
User: marina@easystaff.io, Marina Mikhaylova
```

Claude calls `setup_account({email: "marina@easystaff.io", name: "Marina Mikhaylova"})`:
```
Account created! Your API token is:
mcp_a1b2c3d4e5f6...

IMPORTANT: Save this token — it won't be shown again.
You'll need it to reconnect in future sessions.
```

### Step 3: Connect integrations
```
Claude: Now let's connect your services. Which API keys do you have?
User: I have SmartLead and Apollo keys

Claude calls configure_integration({integration_name: "smartlead", api_key: "eaa086b6-..."})
→ "SmartLead connected. 47 campaigns found."

Claude calls configure_integration({integration_name: "apollo", api_key: "9yIx..."})
→ "Apollo connected."
```

### Step 4: Create first project
```
User: Create a project for EasyStaff Global targeting US IT companies

Claude calls create_project({
  name: "EasyStaff Global - US IT",
  target_segments: "US-based IT services, 50-500 employees",
  target_industries: "IT Services, Software Consulting",
  sender_name: "Marina Mikhaylova",
  sender_company: "easystaff.io"
})
→ "Project created (ID: 1)"
```

### Step 5: First gathering run
```
User: Find IT consulting companies in the US, 50-200 employees

Claude: Before I search, I need a few more details:
- Max pages to fetch? (each page = 25 companies, 1 Apollo credit)
- Any funding stage preference?

User: 4 pages, any funding

Claude calls tam_gather({
  project_id: 1,
  source_type: "apollo.companies.api",
  filters: {
    q_organization_keyword_tags: ["IT consulting"],
    organization_locations: ["United States"],
    organization_num_employees_ranges: ["51,200"],
    max_pages: 4
  }
})
→ "Gathering started. ~100 companies, ~4 credits."
→ "Checkpoint 1 ready — review scope and approve."
```

---

## Via Web UI

### Step 1: Open browser
Navigate to `http://46.62.210.24:3000`

### Step 2: Create account or login
- **New user**: Click "New Account" → enter email + name → click "Sign Up" → token displayed
- **Existing user**: Click "I Have a Token" → paste token → click "Connect"

### Step 3: Connect integrations
- Select service from dropdown (SmartLead, Apollo, etc.)
- Paste API key
- Click "Test & Connect"
- Green dot = connected

---

## Via Claude Code CLI

```bash
# Add MCP server
claude mcp add leadgen --transport sse --url http://46.62.210.24:8002/mcp/sse

# Start conversation
claude

# In conversation:
> Set up my account as Petr, pn@getsally.io
> Connect SmartLead with key eaa086b6-...
> Create project "EasyStaff Global - DACH" targeting SaaS in Germany
> Find SaaS companies in Germany, 50-200 employees, 4 pages max
```

---

## Token Management

- Token format: `mcp_` followed by 64 hex characters
- Shown ONCE at signup — user must save it
- Token stored as bcrypt hash in DB (cannot be recovered)
- If lost: create new account or admin generates new token
- Multiple tokens per account supported (future: name them "laptop", "desktop", etc.)

## What happens without a token

If a user calls any tool (except `setup_account`) without a token:
```json
{"error": "Authentication required. Pass your API token."}
```

The AI should then guide the user to either sign up or provide their token.
