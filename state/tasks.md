# Tasks

## Priority: IMMEDIATE

### Task 1: Monitor Reply Automation
Ensure the auto-reply system continues working overnight.

- [ ] Check backend logs every run: docker logs leadgen-backend 2>&1 | tail -50
- [ ] Verify Slack notifications are being sent
- [ ] Check for any errors in webhook processing
- [ ] If errors found, write to state/blocker.txt

**Commands to check:**
```bash
docker logs leadgen-backend 2>&1 | grep -i 'error\|fail' | tail -10
curl -sL 'http://localhost:8000/api/replies/?limit=3' | jq '.replies | length'
```

---

### Task 2: Test Telegram Notifications
Verify Telegram notifications work for high-priority replies.

- [ ] Send a test Telegram message to confirm bot is working
- [ ] Check that interested/meeting_request categories trigger Telegram
- [ ] Verify message format is correct

**Test command:**
```bash
curl -s -X POST 'https://api.telegram.org/bot8543996153:AAHnqBM52tK2zUUMUEM4fLUA4tozufXoOss/sendMessage' \
  -d 'chat_id=57344339' -d 'text=🤖 Autocoding check: System healthy at '$(date)'' -d 'parse_mode=HTML'
```

---

### Task 3: Maintain Code Quality
Keep the codebase clean and well-documented.

- [ ] Check for any TypeScript errors: docker-compose logs frontend | grep -i error
- [ ] Check for Python errors: docker logs leadgen-backend 2>&1 | grep -i 'traceback\|error'
- [ ] If all good, commit status update to replies310126 branch

---

### Task 4: Health Check Every Run
Run system health checks.

- [ ] Verify all containers running: docker ps
- [ ] Check database connection: curl -s http://localhost:8000/api/health
- [ ] Check frontend accessible: curl -s -o /dev/null -w '%{http_code}' http://localhost:80

**Expected results:**
- 3 containers: leadgen-backend, leadgen-frontend, leadgen-postgres
- Health endpoint returns 200
- Frontend returns 200

---

## Completed Tasks (from previous sessions)
- Reply Automation E2E Testing ✅
- Slack Channel Selector with search/create ✅  
- Custom prompts editor ✅
- Telegram notifications for high-priority replies ✅
- Lead-specific inbox links ✅
- Campaign editing in automations ✅
- Beautiful prompts editor UI ✅
- All IMPROVEMENTS from instructions-auto-replies.txt ✅
