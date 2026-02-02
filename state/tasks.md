# Tasks

## Priority: IMMEDIATE

### Task 1: System Health (SCRIPT) ✅ COMPLETE
Run monitoring script every hour via cron.
Status: Script created at ~/scripts/tasks/monitor_system.sh

---

### Task 2: Improve Reply Processing ✅ COMPLETE
Add better error handling to reply processor.

- [x] Read backend/app/services/reply_processor.py and analyze error handling (done 2026-02-02)
- [x] Add try/catch around Slack notification sending (done 2026-02-02 00:42)
- [x] Add retry logic for failed AI classifications (done 2026-02-02 00:44)
- [x] Write improvements to state/response.txt (done 2026-02-02 00:45)

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
- UX improvements (edit modal, prompts debug) ✅
- Reply processor error handling improvements ✅
