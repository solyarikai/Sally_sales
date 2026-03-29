# Telegram Bot Test Results

**Date**: 2026-03-29 08:22
**Bot**: @sallymcptestbot
**Results**: 11/12 passed

## Failures

### 08. Find companies
- **Sent**: find IT consulting companies in Miami, 5-50 employees, just 1 page
- **Reply**: It looks like there was an issue with the project. Let me recreate the project or verify the existing one first.   Would you like me to recreate the p
- **Reason**: Expected any of: ['gathering', 'companies', 'started', 'checkpoint', 'found', 'blacklist']

## All Results

| # | Test | Status | Reply |
|---|------|--------|-------|
| ✓ | 01. /start | PASS | Welcome to LeadGen MCP Bot!  I help you find companies, buil... |
| ✓ | 02. Login | PASS | You're logged in as Test User. Let's set up a campaign!   Fi... |
| ✓ | 03. Connect SmartLead | PASS | Smartlead has been successfully connected! I found 1975 camp... |
| ✓ | 04. Connect Apollo | PASS | Apollo has been successfully connected! What would you like ... |
| ✓ | 05. Connect OpenAI | PASS | It seems OpenAI has been successfully connected!   If there'... |
| ✓ | 06. Verify integrations | PASS | Here are your integrations:  1. **OpenAI**: Connected 2. **S... |
| ✓ | 07. Create project | PASS | Project **"EasyStaff Test"** has been created. The website [... |
| ✗ | 08. Find companies | FAIL | It looks like there was an issue with the project. Let me re... |
| ✓ | 09. Approve checkpoint 1 | PASS | Project **"EasyStaff Test"** has been recreated successfully... |
| ✓ | 10. Check pipeline status | PASS | Your pipeline status shows you have:  - **3 Projects**: Easy... |
| ✓ | 11. Check contacts | PASS | You currently have **0 contacts** and **0 companies** in you... |
| ✓ | 12. Check replies | PASS | You currently have **0 warm replies** in your database.   Is... |
