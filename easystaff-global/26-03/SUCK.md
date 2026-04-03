# What I Suck At — Don't Repeat These Mistakes

**Date**: 2026-03-26

---

## MISTAKE 1: Searched `LIKE '%Petr ES%'` instead of `ILIKE '%petr%'`

**What happened**: Analyzed only 8 "Petr ES" campaigns but there are 11 Petr campaigns total. Missed:
- `UAE-Pakistan Petr 16/03 - copy` — had Dileep (INTERESTED, asked for deck)
- `UAE-Pakistan Petr 16/03 - copy - copy` — 26 replies
- `AU-Philippines Petr 19/03` — had Jerome (QUESTION about staffing), Orville (INTERESTED, liked message)
- `Petr - EasyStaff - Gulf SA Diaspora Mar26` — 13 replies

**Result**: Reported 4 warm replies when there were actually 9. Missed 5 warm leads including Dileep (ThinkChain, interested, asked for deck).

**Fix**: ALWAYS search `campaign_name ILIKE '%petr%'` — case-insensitive, catches all naming patterns. Never assume campaign naming convention.

---

## MISTAKE 2: Didn't check ALL campaign naming patterns

**What happened**: Assumed all Petr campaigns follow "Petr ES [Region]" pattern. Reality:
- `Petr ES APAC` — yes
- `UAE-Pakistan Petr 16/03 - copy` — Petr is in the MIDDLE
- `AU-Philippines Petr 19/03` — same
- `Petr - EasyStaff - Gulf SA Diaspora Mar26` — different prefix

**Fix**: Start every campaign analysis by listing ALL campaigns matching the operator name with `ILIKE '%name%'`. Don't filter by prefix pattern.

---

## MISTAKE 3: Excluded test reply (pn@getsally.io) without noting it

**What happened**: One "interested" reply was from pn@getsally.io — test email. Should have been flagged and excluded explicitly, not silently counted.

**Fix**: Always filter out `pn@getsally.io` explicitly AND note it: "1 test reply excluded (pn@getsally.io)".

---

## MISTAKE 4: Didn't verify reply classification accuracy

**What happened**: Trusted the `category` column without reading the actual reply text. Some classifications may be wrong:
- Matt Hodgson classified as `meeting_request` but it's actually an OOO auto-reply
- Orville Dave classified as `interested` but it's just a LinkedIn-style "like" reaction

**Fix**: For warm replies analysis, ALWAYS read the actual `reply_text` and verify the classification makes sense. Don't just aggregate counts.

---

## MISTAKE 5: Built SmartLead links with wrong URL pattern

**What happened**: Used `https://app.smartlead.ai/app/email-campaigns-v2/{id}/lead/{email}` — not a real endpoint.

**Fix**: The correct pattern is `https://app.smartlead.ai/app/master-inbox?leadMap={lead_map_id}`. Get it from `processed_replies.inbox_link` column — it's already stored in the DB.

---

## CHECKLIST: Before Reporting Campaign Replies

1. [ ] Search ALL campaigns: `campaign_name ILIKE '%operator_name%'`
2. [ ] List all found campaigns FIRST, confirm with user
3. [ ] Exclude test emails (pn@getsally.io)
4. [ ] Read actual reply_text for warm replies — verify classification
5. [ ] Use `inbox_link` from DB for SmartLead links — never construct manually
6. [ ] Count: total replies, OOO, unsubscribe, real replies, warm (meeting+interested+question)
7. [ ] For warm replies: show full text, SmartLead link, company domain, received date
