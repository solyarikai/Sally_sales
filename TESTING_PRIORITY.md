# PRIORITY: END-TO-END TESTING

## IMMEDIATE TASK

Test the complete reply automation flow:

1. **Slack Integration** - MUST work with bot token
   - Token: SLACK_BOT_TOKEN in .env
   - Test channel: #c-replies-test (ID: C09REGUQWTG)
   - Use `chat.postMessage` API, NOT webhooks

2. **Smartlead Webhook** - Test receiving replies
   - Endpoint: POST /api/smartlead/webhook
   - Simulate a reply event
   - Verify it gets processed

3. **AI Classification** - Verify it works
   - Test with sample email content
   - Check categories are assigned correctly

## Slack Notification Service FIX

Update backend/app/services/notification_service.py to use BOT TOKEN:

```python
import os
import httpx

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

async def send_slack_notification(channel_id: str, reply_data: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "channel": channel_id,
                "text": f"New reply from {reply_data['from_email']}",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*New Email Reply*\n*From:* {reply_data['from_email']}\n*Category:* {reply_data['category']}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Message:*\n>{reply_data['body'][:500]}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*AI Draft Reply:*\n{reply_data.get('draft_reply', 'N/A')}"
                        }
                    }
                ]
            }
        )
        return response.json()
```

## Test the Webhook

Create a test endpoint or use curl to simulate:

```bash
# Test webhook endpoint
curl -X POST http://localhost:8000/api/smartlead/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "EMAIL_REPLIED",
    "campaign_id": 123,
    "lead": {
      "email": "test@example.com",
      "first_name": "John",
      "last_name": "Doe"
    },
    "email": {
      "subject": "Re: Partnership Opportunity",
      "body": "Hi, I am very interested in learning more about your services. When can we schedule a call?",
      "from_email": "test@example.com",
      "to_email": "your@email.com"
    }
  }'
```

## Create Test Endpoint

Add to backend/app/api/replies.py:

```python
@router.post("/test-notification")
async def test_notification():
    """Test the Slack notification with sample data"""
    from ..services.notification_service import send_slack_notification
    
    test_data = {
        "from_email": "test@example.com",
        "category": "interested",
        "body": "I am very interested in your services. Let's schedule a call!",
        "draft_reply": "Thank you for your interest! I'd be happy to schedule a call. What times work best for you?"
    }
    
    result = await send_slack_notification("C09REGUQWTG", test_data)
    return {"slack_response": result}
```

## Definition of Done

- [ ] Slack message sent to #c-replies-test successfully
- [ ] Webhook endpoint processes test reply
- [ ] AI classifies reply correctly
- [ ] Reply appears in /replies dashboard
- [ ] Update status.txt to DONE when all working

## IMPORTANT

- Use SLACK_BOT_TOKEN from .env (not webhook URL)
- Channel ID: C09REGUQWTG
- DO NOT skip any step - test everything end-to-end
