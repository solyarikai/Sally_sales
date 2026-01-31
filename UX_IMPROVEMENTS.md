# UX Improvements for Reply Automation

## CRITICAL SAFETY RULES

### 1. Google Sheets Safety
- **NEVER modify existing Google Sheets**
- **ONLY create NEW sheets** for test purposes
- When user selects "existing sheet" - show warning and require confirmation
- Default: Always suggest creating a new sheet
- Name format: `Replies_[AutomationName]_[Date]`

### 2. Smartlead Safety  
- **NEVER send any messages via Smartlead API**
- **READ-ONLY mode** - only fetch campaigns, leads, and messages
- No `POST` to any Smartlead send endpoints
- All "Send Reply" buttons are **preview-only** (prepare UX, don't execute)

---

## UX Vision: Simple Setup for Salespeople

### Goal
A salesperson should be able to set up reply automation in **under 2 minutes** with a chat-like wizard.

---

## Improved Setup Flow (Chat-Style Wizard)

### Step 1: Welcome & Campaign Selection
```
┌─────────────────────────────────────────────────────────┐
│  🤖 Let's set up your Reply Automation                  │
│                                                         │
│  Which Smartlead campaigns should I monitor for         │
│  replies?                                               │
│                                                         │
│  🔍 [Search campaigns...]                               │
│                                                         │
│  ☑️ EasyStaff - Email Campaign (234 leads)              │
│  ☐ Tech Outreach Q1 (156 leads)                        │
│  ☑️ Partner Program (89 leads)                          │
│  ☐ Cold Outreach Feb (412 leads)                       │
│                                                         │
│  [Continue →]                                           │
└─────────────────────────────────────────────────────────┘
```

### Step 2: Google Sheets (Optional)
```
┌─────────────────────────────────────────────────────────┐
│  📊 Where should I log replies?                         │
│                                                         │
│  ○ Create new Google Sheet (Recommended)               │
│    └─ Name: Replies_MyAutomation_Jan2026               │
│                                                         │
│  ○ Skip Google Sheets for now                          │
│                                                         │
│  ○ Use existing sheet (⚠️ Advanced)                    │
│    └─ [Select sheet...]                                │
│    └─ ⚠️ Warning: Only new rows will be added          │
│                                                         │
│  [← Back] [Continue →]                                  │
└─────────────────────────────────────────────────────────┘
```

### Step 3: Slack Channel
```
┌─────────────────────────────────────────────────────────┐
│  💬 Where should I send reply notifications?            │
│                                                         │
│  🔍 [Search channels...]                                │
│                                                         │
│  • #c-replies-test                                      │
│  • #sales-notifications                                 │
│  • #team-outreach                                       │
│                                                         │
│  Selected: #c-replies-test ✓                           │
│                                                         │
│  [← Back] [Continue →]                                  │
└─────────────────────────────────────────────────────────┘
```

### Step 4: Review & Activate
```
┌─────────────────────────────────────────────────────────┐
│  ✅ Ready to activate!                                  │
│                                                         │
│  📋 Summary:                                            │
│  • Monitoring: 2 campaigns                              │
│  • Logging to: Replies_MyAutomation_Jan2026 (new)      │
│  • Notifications: #c-replies-test                       │
│                                                         │
│  🔒 Safety: Read-only mode - no auto-replies           │
│                                                         │
│  [← Back] [🚀 Activate Automation]                      │
└─────────────────────────────────────────────────────────┘
```

---

## Slack Notification with Approval Flow

### When Reply Arrives → Show in Slack
```
┌─────────────────────────────────────────────────────────┐
│  🟢 New Reply - Interested                              │
│  ───────────────────────────────────────────────────── │
│  From: John Doe (Acme Corp)                            │
│  Campaign: EasyStaff - Email Campaign                  │
│  ───────────────────────────────────────────────────── │
│  Original Message:                                      │
│  "Hi! I'm very interested in learning more about       │
│   your platform. Can we schedule a call this week?"    │
│  ───────────────────────────────────────────────────── │
│  💡 Suggested Reply:                                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Hi John,                                         │   │
│  │                                                  │   │
│  │ Thank you for your interest! I'd be happy to    │   │
│  │ schedule a call. How does Thursday at 2 PM work?│   │
│  │                                                  │   │
│  │ Best regards,                                    │   │
│  │ [Your Name]                                      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  [✅ Approve] [✏️ Edit] [❌ Dismiss] [📋 View Thread]   │
│                                                         │
│  ⚠️ Note: Approval prepares reply for review.          │
│     Manual sending required.                            │
└─────────────────────────────────────────────────────────┘
```

### Button Actions (UX Ready, No Auto-Send)

| Button | Action |
|--------|--------|
| **✅ Approve** | Marks reply as approved, copies to clipboard, opens Smartlead draft (NO auto-send) |
| **✏️ Edit** | Opens modal to edit suggested reply |
| **❌ Dismiss** | Marks as handled, no action needed |
| **📋 View Thread** | Shows full email conversation |

---

## Slack Interactive Features (Implement These)

### 1. Slash Command Setup
```
/setup-replies
```
Launches the chat-style wizard directly in Slack.

### 2. Quick Actions
```
/reply-stats
```
Shows daily/weekly reply statistics.

### 3. Approval Modal (When "Approve" clicked)
```
┌─────────────────────────────────────────────────────────┐
│  ✅ Reply Approved                                      │
│                                                         │
│  The suggested reply has been:                         │
│  ☑️ Copied to clipboard                                │
│  ☑️ Logged to Google Sheet                             │
│  ☑️ Marked as "Approved" in dashboard                  │
│                                                         │
│  🔗 Open in Smartlead to send manually:                │
│  [Open Smartlead →]                                     │
│                                                         │
│  ⚠️ Auto-send is disabled for safety.                  │
│     Please send manually in Smartlead.                  │
└─────────────────────────────────────────────────────────┘
```

---

## Dashboard UX Improvements

### Replies Dashboard (`/replies`)

```
┌─────────────────────────────────────────────────────────────────────┐
│  📬 Reply Automation                              [+ New Automation] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Today: 12 replies │ 8 interested │ 2 meetings │ 2 other            │
│                                                                      │
├──────────────┬──────────────────────────────────────────────────────┤
│ AUTOMATIONS  │  RECENT REPLIES                                       │
├──────────────┼──────────────────────────────────────────────────────┤
│              │                                                       │
│ ✅ EasyStaff │  🟢 John Doe (Acme) - Interested        2 min ago    │
│    2 camps   │     "Can we schedule a call?"                        │
│              │     [Approved ✓] [View Draft]                        │
│              │  ─────────────────────────────────────────────       │
│ ⏸️ Partner   │  📅 Sarah Lee (Tech Inc) - Meeting      15 min ago   │
│    1 camp    │     "Thursday works for me"                          │
│              │     [Pending] [Approve] [Edit]                       │
│              │  ─────────────────────────────────────────────       │
│ [+ Add]      │  🔴 Mike Chen (StartupXYZ) - Not interested 1 hr ago │
│              │     "We already have a solution"                     │
│              │     [Dismissed]                                       │
│              │                                                       │
└──────────────┴──────────────────────────────────────────────────────┘
```

---

## Technical Implementation

### 1. Slack Interactivity (Add to backend)

```python
# backend/app/api/slack_interactions.py

@router.post("/slack/interactions")
async def handle_slack_interaction(payload: dict):
    """Handle Slack button clicks"""
    action = payload.get("actions", [{}])[0]
    action_id = action.get("action_id")
    
    if action_id == "approve_reply":
        reply_id = action.get("value")
        # Mark as approved
        # Log to Google Sheet
        # Return success modal
        # DO NOT send to Smartlead
        
    elif action_id == "edit_reply":
        # Open edit modal
        
    elif action_id == "dismiss_reply":
        # Mark as dismissed
```

### 2. Google Sheets Service (Safe Mode)

```python
# backend/app/services/google_sheets_service.py

class GoogleSheetsService:
    async def create_new_sheet(self, name: str) -> str:
        """Create a NEW sheet - safe operation"""
        # Always creates new, never modifies existing
        pass
    
    async def append_row(self, sheet_id: str, row_data: dict):
        """Append row to sheet - safe, only adds data"""
        # Only appends, never updates/deletes
        pass
    
    # NO update_row or delete_row methods - safety by design
```

### 3. Slack Message Builder

```python
# backend/app/services/slack_message_builder.py

def build_reply_notification(reply) -> dict:
    """Build Slack message with interactive buttons"""
    return {
        "blocks": [
            # Header with category
            # Lead info
            # Original message
            # Suggested reply in code block
            # Action buttons
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve"},
                        "style": "primary",
                        "action_id": "approve_reply",
                        "value": str(reply.id)
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✏️ Edit"},
                        "action_id": "edit_reply",
                        "value": str(reply.id)
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Dismiss"},
                        "action_id": "dismiss_reply",
                        "value": str(reply.id)
                    }
                ]
            }
        ]
    }
```

---

## Priority Order for Implementation

1. **P0 - Safety**
   - Google Sheets: Create new only, no existing sheet modifications
   - Smartlead: Hardcode READ-ONLY mode, remove any send capabilities

2. **P1 - Slack Buttons**
   - Add interactive buttons to notifications
   - Handle button clicks (approve/edit/dismiss)
   - Show confirmation modals

3. **P2 - Chat Wizard**
   - Convert setup form to step-by-step chat flow
   - Add inline search for campaigns/channels
   - Show summary before activation

4. **P3 - Dashboard Polish**
   - Real-time updates
   - Quick filters
   - Bulk actions

---

## Definition of Done

- [ ] Google Sheets: Only creates new sheets, never modifies existing
- [ ] Smartlead: 100% read-only, no send capabilities in code
- [ ] Slack notifications have Approve/Edit/Dismiss buttons
- [ ] Clicking Approve shows success modal + copies draft
- [ ] Setup wizard is step-by-step (max 4 steps)
- [ ] Dashboard shows reply status (pending/approved/dismissed)
- [ ] All tested end-to-end

---

## CONCISE SLACK NOTIFICATIONS (IMPORTANT!)

Keep notifications SHORT and actionable. Current format is too verbose.

### Target Format (Max 6 lines total):



### Formatting Rules:
1. **Line 1:** Emoji + Category + Name + Company (one line)
2. **Line 2-3:** Message preview (max 100 chars, truncate with ...)  
3. **Line 4-5:** Draft preview (max 100 chars)
4. **Line 6:** Buttons - use short labels: OK / Edit / Skip

### Category Emojis (single emoji):
- 🟢 Interested
- 📅 Meeting
- 🔴 Not interested
- 🏖️ Out of office
- ❓ Question
- 📧 Other

### NO verbose headers like:
- ❌ New Email Reply - Meeting Request
- ❌ From: ... Campaign: ... Subject: ...
- ❌ Original Message: ... Suggested Reply: ...

### YES concise format:
- ✅ One-line header with all key info
- ✅ Quoted message snippet
- ✅ Quoted draft snippet  
- ✅ Action buttons

