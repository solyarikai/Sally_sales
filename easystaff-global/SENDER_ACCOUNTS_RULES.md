# EasyStaff Global — Sender Accounts Rules

## Source of Truth

**Google Sheet**: `1MepWTwCGJX-fGQPkygQouF-hfL8WYV4DRAdmqI3DbDg`
**Tab**: "Accounts infra" (gid=1462088713)
**Access**: via service account (shared Drive)

## Account Assignment Rules

The "Source" column in the sheet determines who MANAGES the inbox profile (Ksenia, Petr, Pavel, Sonya).
The EMAIL PREFIX determines the SENDER NAME the recipient sees:
- `petr@...` or `petr.n@...` → Sender name: **Petr Nikolaev**
- `rinat@...` or `rinat.k@...` → Sender name: **Rinat Karimov**

## Accounts by Source (from sheet, read 2026-03-22)

### Source = "Petr" (33 inboxes)
```
rinat.k@crona-hq.com
rinat.k@growwith-crona.com
petr@crona-track.com
petr@prospects-crona.com
rinat@crona-b2b.com
rinat@crona-base.com
rinat@crona-force.com
rinat@crona-flow.com
rinat@segment-crona.com
rinat@leads-crona.com
rinat@prospects-crona.com
rinat@crona-stack.com
rinat@crona-track.com
rinat@growth-crona.com
petr@cronaaidata.com
petr@cronaaisegment.com
petr@cronaaitarget.com
rinat@cronaaidata.com
rinat@cronaaitarget.com
rinat@cronaaileads.com
rinat@cronaaipipeline.com
rinat@cronaaiprospects.com
petr@cronaaiedge.com
petr@cronaaiflow.com
petr@cronaaiforce.com
petr@cronaaihq.com
petr@cronaaireach.com
petr@cronaaisales.com
petr@cronaaisync.com
petr@cronaaitrack.com
petr@growthcronaai.com
petr@growwithcronaai.com
petr@leadscronaai.com
```

### Source = "Pavel" (15 inboxes)
```
petr@scalecronaai.com
petr@usecronaai.com
rinat@cronaaiedge.com
rinat@cronaaiflow.com
rinat@cronaaiforce.com
rinat@cronaaihq.com
rinat@cronaaireach.com
rinat@cronaaisales.com
rinat@cronaaisync.com
rinat@cronaaitrack.com
rinat@growthcronaai.com
rinat@growwithcronaai.com
rinat@leadscronaai.com
rinat@scalecronaai.com
rinat@usecronaai.com
```

## Campaign Rules

1. **Use ALL accounts from Source = "Petr" AND Source = "Pavel"** (48 total) for EasyStaff Global campaigns
2. **Sonya and Ksenia accounts are NOT used** for EasyStaff Global — different projects
3. **ONE set of inboxes** connected to ALL timezone campaigns — SmartLead distributes balanced
4. **Sender name** = auto from inbox settings (`{{Sender Name}}` SmartLead variable)
5. **Signature** removed from inbox level, use `{{Sender Name}}` in sequence body

## How to Connect Inboxes to Campaign via API

```
POST /api/v1/campaigns/{campaign_id}/email-accounts?api_key={KEY}
{"email_account_ids": [id1, id2, ...]}
```

To get inbox IDs: `GET /api/v1/email-accounts?api_key={KEY}&limit=100&offset=0`
Match by `from_email` field against the lists above.
