# Reply Notification Flow

## Pipeline

```
Inbound Reply (SmartLead webhook OR GetSales webhook OR sync poll)
    ↓
reply_processor.py: process_smartlead_reply() / process_getsales_reply()
    ↓
1. Dedup check (COALESCE key + message_hash)
2. Classify (AI → category + confidence)
3. Generate draft (Gemini 2.5 Pro)
4. Detect language + translate if needed
5. Store ProcessedReply
    ↓
notification_service.py: send_telegram_notification()
    ↓
Telegram message with:
    - Category badge (color + label)
    - Lead name + email (if real)
    - Campaign + Project + Sender
    - Message body
    - Deep link: /tasks/replies?reply_id={id}&project={name}
    - Platform link (SmartLead or GetSales)
```

## Deep Link Construction

### Telegram "Open in Replies UI"

```python
replies_ui_url = f"{FRONTEND_URL}/tasks/replies?reply_id={reply.id}&project={project_slug}"
```

Always uses `reply_id` — works for email leads AND LinkedIn leads without email.

The `project` parameter is CRITICAL — without it, the frontend defaults to the wrong project and shows "All caught up" (empty).

### Project Slug

```python
project_slug = quote(project['name'].lower().replace(' ', '-'))
# "easystaff ru" → "easystaff-ru"
# "inxy" → "inxy"
```

### Platform Links

| Platform | Link |
|----------|------|
| SmartLead | `https://app.smartlead.ai/app/master-inbox` (or campaign-specific) |
| GetSales | `https://amazing.getsales.io/messenger/{contact_uuid}` |

## Notification Routing

How the system determines which project a reply belongs to:

```
Campaign Name
    ↓
Step 1: Exact match in project.campaign_filters JSON array
    ↓ (not found)
Step 2: Longest prefix match (campaign starts with project name)
    ↓ (not found)
Step 3: DB lookup — campaigns table → project_id
    ↓ (not found, GetSales only)
Step 4: Sender UUID match — project.getsales_senders
    ↓ (not found)
Unrouted → goes to default channel
```

## Telegram Message Format

### Standard (most projects)
```
🟢 🔗 Meeting Request

From: Emily Friedman
Email: emily@fpm-na.com
Campaign: TFP — Fashion brands Clay base
Project: tfp
Sender: Dias Nurlanov

Message:
This sounds very interesting. Do you have time for a brief call?

📋 Open in Replies UI  ·  📬 Open in SmartLead
```

### LinkedIn (no email)
```
🟢 🔗 Interested

From: Станислав Malynovskyy
Campaign: EasyStaff - Russian DM [>500 connects]
Project: easystaff ru
Sender: Sergey Lebedev

Message:
Здравствуйте, Сергей! Давайте, расскажите)

📋 Open in Replies UI
🏢 Open in GetSales
```

Note: No "Email:" line for LinkedIn leads without email.

## Compact Format (Project-Specific)

Projects can opt into compact notifications via `project.telegram_notification_config`:

```
💼 LinkedIn · 🟢 Interested
Станислав Malynovskyy
EasyStaff - Russian DM [>500 connects] · Sergey Lebedev
Здравствуйте, Сергей! Давайте, расскажите)

📋 Open in Replies UI  ·  🏢 Open in GetSales
```
