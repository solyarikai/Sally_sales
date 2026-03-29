# Telegram Bot Test Results

**Date**: 2026-03-29 08:11
**Bot**: @sallymcptestbot
**Results**: 7/12 passed

## Failures

### 03. Connect SmartLead
- **Sent**: connect smartlead with key eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5
- **Reply**: You're logged in as Test User! 🎉  Now, let's set up your campaign. Please provide the following details: 1. Keywords 2. Location 3. Size (e.g. small, 
- **Reason**: Expected any of: ['connected', 'SmartLead', 'campaigns found', 'success']

### 04. Connect Apollo
- **Sent**: connect apollo with key 9yIx2mZegixXHeDf6mWVqA
- **Reply**: You're logged in as Test User! 🎉  Now, let's set up your campaign. Please provide the following details: 1. Keywords 2. Location 3. Size (e.g. small, 
- **Reason**: Expected any of: ['connected', 'Apollo', 'success']

### 05. Connect OpenAI
- **Sent**: connect openai with key sk-proj-VKUrN5_Ut2cmuoggW_3NF0FBEk4lS3j6VRHWbNw-Zwv7p_rEWwjQhimiOzdAHreUiH9L
- **Reply**: You're logged in as Test User! 🎉  Now, let's set up your campaign. Please provide the following details: 1. Keywords 2. Location 3. Size (e.g. small, 
- **Reason**: Expected any of: ['connected', 'OpenAI', 'success', 'saved']

### 06. Verify integrations
- **Sent**: show my integrations
- **Reply**: You're logged in as Test User! 🎉  Now, let's set up your campaign. Please provide the following details: 1. Keywords 2. Location 3. Size (e.g. small, 
- **Reason**: Expected any of: ['SmartLead', 'Apollo', 'connected']

### 07. Create project
- **Sent**: create project EasyStaff Test with website easystaff.io targeting IT outsourcing companies in Miami,
- **Reply**: Error:
- **Reason**: Expected any of: ['created', 'project', 'EasyStaff']

## All Results

| # | Test | Status | Reply |
|---|------|--------|-------|
| ✓ | 01. /start | PASS | Welcome to LeadGen MCP Bot!  I help you find companies, buil... |
| ✓ | 02. Login | PASS | You're logged in as Test User! 🎉  Now, let's set up your cam... |
| ✗ | 03. Connect SmartLead | FAIL | You're logged in as Test User! 🎉  Now, let's set up your cam... |
| ✗ | 04. Connect Apollo | FAIL | You're logged in as Test User! 🎉  Now, let's set up your cam... |
| ✗ | 05. Connect OpenAI | FAIL | You're logged in as Test User! 🎉  Now, let's set up your cam... |
| ✗ | 06. Verify integrations | FAIL | You're logged in as Test User! 🎉  Now, let's set up your cam... |
| ✗ | 07. Create project | FAIL | Error:... |
| ✓ | 08. Find companies | PASS | We'll create a draft campaign for IT consulting companies in... |
| ✓ | 09. Approve checkpoint 1 | PASS | I'll create the draft campaign with the specified details. L... |
| ✓ | 10. Check pipeline status | PASS | Your pipeline status shows no active campaigns at the moment... |
| ✓ | 11. Check contacts | PASS | You have a total of **8,441 contacts** and **7,555 companies... |
| ✓ | 12. Check replies | PASS | You currently have **0 warm replies** for your project **Eas... |
