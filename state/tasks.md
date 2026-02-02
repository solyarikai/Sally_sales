# Tasks

## Priority: IMMEDIATE

### Task 1: System Health (SCRIPT)
Run monitoring script every hour via cron.
Status: ✅ COMPLETE - Script created at ~/scripts/tasks/monitor_system.sh

---

### Task 2: Improve Reply Processing
Add better error handling to reply processor.

- [ ] Read backend/app/services/reply_processor.py and analyze error handling
- [ ] Add try/catch around Slack notification sending
- [ ] Add retry logic for failed AI classifications
- [ ] Write improvements to state/response.txt

---

### Task 3: Add Reply Statistics Endpoint
Create an endpoint to get reply statistics per automation.

- [ ] Create GET /api/replies/stats endpoint in backend
- [ ] Return counts: total, by_category, by_automation
- [ ] Add to frontend dashboard

---

### Task 4: Optimize Docker Build
Reduce Docker build time for faster deployments.

- [ ] Add .dockerignore if not present
- [ ] Use multi-stage builds
- [ ] Cache pip dependencies layer

---

## Completed Tasks
- System monitoring script ✅
- Continuous runner with auto git commit/push ✅
- Reply automation E2E testing ✅
- Slack channel selector ✅
- Telegram notifications ✅
