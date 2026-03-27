# Spam Filter Report

## Overview
The Spam filter report endpoint provides detailed spam scoring analysis per sender mailbox. Each spam score includes contributing rules and details. Ideally, spam scores should be close to 0 or less.

## Endpoint Details

**HTTP Method:** GET

**URL:** `https://smartdelivery.smartlead.ai/api/v1/spam-test/report/$(spamTestId)/spam-filter-details`

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | Yes | `API_KEY` | Your API authentication key |
| `spamTestId` | integer | Yes | N/A | The ID of the spam test |

---

## Request Example

```bash
curl --location -g 'https://smartdelivery.smartlead.ai/api/v1/spam-test/report/7268/spam-filter-details?api_key=$(API_KEY)'
```

---

## Response Examples

### Success Response (200)

```json
[
  {
    "from_email": "harrisonmarganza@outlook.com",
    "spam_filter_details": [
      {
        "spam_filter_result": {
          "contentPreview": "How's the sales environment treating you as I may be wrong,",
          "detailedRules": [
            {
              "ruleDescription": "RBL: ADMINISTRATOR NOTICE: The query to",
              "ruleName": "RCVD_IN_ZEN_BLOCKED_OPENDNS",
              "ruleScore": 0
            },
            {
              "ruleDescription": "SPF: HELO does not publish an SPF Record",
              "ruleName": "SPF_HELO_NONE",
              "ruleScore": 0
            },
            {
              "ruleDescription": "Message has a DKIM or DK signature, not necessarily valid",
              "ruleName": "DKIM_SIGNED",
              "ruleScore": 0.1
            },
            {
              "ruleDescription": "Message has a valid ARC signature",
              "ruleName": "ARC_VALID",
              "ruleScore": -0.1
            },
            {
              "ruleDescription": "DKIM or DK signature exists, but is not valid",
              "ruleName": "DKIM_INVALID",
              "ruleScore": 0.1
            },
            {
              "ruleDescription": "Sender email is commonly abused enduser mail provider",
              "ruleName": "FREEMAIL_FROM",
              "ruleScore": 0
            },
            {
              "ruleDescription": "BODY: HTML included in message",
              "ruleName": "HTML_MESSAGE",
              "ruleScore": 0
            },
            {
              "ruleDescription": "DMARC none policy",
              "ruleName": "DMARC_NONE",
              "ruleScore": 0.9
            },
            {
              "ruleDescription": "No description available.",
              "ruleName": "SPOOFED_FREEMAIL",
              "ruleScore": 1
            }
          ],
          "isSpam": true,
          "required": 5,
          "score": 2
        },
        "score": 2,
        "required": 5
      }
    ]
  }
]
```

### Error Response (400)

```json
{}
```

---

## Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `from_email` | string | Sender email address |
| `spam_filter_details` | array | Array of spam filter analysis results |
| `spam_filter_result.contentPreview` | string | Preview of email content analyzed |
| `spam_filter_result.detailedRules` | array | Individual spam rules evaluated |
| `detailedRules[].ruleDescription` | string | Human-readable explanation of the rule |
| `detailedRules[].ruleName` | string | Machine name of the spam rule |
| `detailedRules[].ruleScore` | number | Numeric score contribution from this rule |
| `spam_filter_result.isSpam` | boolean | Whether message classified as spam |
| `spam_filter_result.required` | integer | Required score threshold for spam classification |
| `spam_filter_result.score` | integer | Computed spam score for the message |

## Key Notes

- Lower spam scores indicate better deliverability
- Negative scores are favorable
- The `required` threshold indicates the cutoff for spam classification
- Individual rule scores contribute to the total email spam assessment
- Results are broken down per sender mailbox
