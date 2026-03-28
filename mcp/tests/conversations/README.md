# MCP Conversation Tests

## Architecture

Each test file = one user journey as a conversation.

```
tests/conversations/
  01_new_user_easystaff.json     — User 1: existing campaigns, 2 segments
  02_new_user_fashion.json       — User 2: no campaigns, fashion brands
  03_add_more_targets.json       — User asks to gather more for existing pipeline
  04_edit_sequence.json          — User edits sequence after reviewing
  05_activate_campaign.json      — User approves and activates
```

## Test File Structure

```json
{
  "id": "01_new_user_easystaff",
  "description": "New user with existing SmartLead campaigns sets up EasyStaff project",
  "user_email": "pn@getsally.io",
  "user_password": "qweqweqwe",

  "steps": [
    {
      "step": 1,
      "user_prompt": "My website is https://easystaff.io/. Set up a project called EasyStaff-Global",
      "user_prompt_variants": [
        "Create project EasyStaff-Global, website easystaff.io",
        "I need a project for EasyStaff, here's our site: https://easystaff.io/"
      ],
      "expected_tool_calls": ["create_project"],
      "expected_behavior": {
        "tool_args": {"website": "https://easystaff.io/"},
        "response_must_contain": ["project", "created", "website", "scraped"],
        "response_must_not_contain": ["error", "failed"],
        "links_expected": false
      }
    },
    {
      "step": 2,
      "user_prompt": "Find IT consulting and media production companies in Miami",
      "user_prompt_variants": [
        "Gather IT consulting + media production firms, Miami area",
        "I need leads from IT consulting and also video production companies in Miami FL"
      ],
      "expected_tool_calls": ["parse_gathering_intent", "tam_gather", "tam_gather"],
      "expected_behavior": {
        "parse_intent_segments": 2,
        "segment_labels": ["IT_CONSULTING", "MEDIA_PRODUCTION"],
        "pipelines_created": 2,
        "response_must_contain": ["2 segments", "IT", "media", "Miami"]
      }
    }
  ],

  "final_verification": {
    "ui_screenshots": [
      {"page": "/pipeline", "check": "2 runs visible with segment badges"},
      {"page": "/conversations", "check": "all tool calls logged with both directions"},
      {"page": "/projects", "check": "EasyStaff-Global project with campaigns"}
    ],
    "db_checks": [
      "projects.target_segments contains website scrape",
      "discovered_companies has no duplicate domains",
      "mcp_conversation_logs has entries for every tool call"
    ]
  }
}
```

## How Testing Works

1. **Load test file** — get user prompts and expected behavior
2. **Shuffle prompts** — pick random variant (same intent, different wording)
3. **Execute via REST /tool-call** — real MCP protocol, logged to conversations
4. **Compare actual vs expected**:
   - Did the right tools get called? (tool_calls match)
   - Did the response contain required fields? (must_contain)
   - Were links included where expected? (links_expected)
   - Were segments correctly split? (segment_labels)
5. **Score** — percentage match on each dimension
6. **Screenshot UI pages** — verify visual state matches expected
7. **Check conversations page** — all messages visible

## Scoring

| Dimension | Weight | How scored |
|-----------|--------|------------|
| Correct tools called | 30% | Exact match on tool sequence |
| Response structure | 25% | Must-contain fields present |
| Links included | 15% | Expected links in response |
| Segment accuracy | 15% | Labels match user intent |
| No errors | 15% | No error/failed in response |

**Pass threshold**: 80% overall score
**God threshold**: 95% overall score
