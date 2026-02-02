# CRM Sync - Smartlead + GetSales Integration

Unified CRM that merges contacts from Smartlead and GetSales by matching LinkedIn URLs or emails.

## Quick Start

```bash
cd scripts
./sync_crm.sh
```

This will:
1. ✅ Fetch 1000 recent contacts from Smartlead
2. ✅ Fetch 1000 recent contacts from GetSales  
3. ✅ Merge them by LinkedIn URL or email
4. ✅ Import to database (if backend is running)

## View in UI

Open http://localhost:5173/contacts to see your CRM with all contacts.

**Filters available:**
- **Status**: lead, contacted, replied, qualified, customer, lost
- **Source**: smartlead, getsales, smartlead+getsales, csv, manual
- **Segment**: iGaming, B2B SaaS, FinTech, etc.
- **Project**: Group contacts by project
- **Search**: Search by name, email, company, title

## Scripts

### Individual Scripts

```bash
# Fetch Smartlead only
python3 fetch_smartlead_contacts.py

# Fetch GetSales only  
python3 fetch_getsales_contacts.py

# Merge existing JSON files
python3 merge_contacts.py
```

### Output Files

- `smartlead_contacts.json` - Raw Smartlead contacts
- `getsales_contacts.json` - Raw GetSales contacts
- `merged_contacts.json` - Merged and deduplicated contacts

## Merge Logic

Contacts are matched by:
1. **LinkedIn URL** (primary) - Normalized to username
2. **Email** (secondary) - Case-insensitive

If a contact exists in both sources, data is merged with priority:
- Smartlead data for campaign info
- GetSales data for enrichment (title, location, etc.)

## API Credentials

Set in `backend/.env`:

```env
SMARTLEAD_API_KEY=your-key-here
GETSALES_API_KEY=your-key-here
```

## Database Schema

Contacts are stored in the `contacts` table with fields:
- email, first_name, last_name
- company_name, domain, job_title
- segment, project_id
- source (smartlead, getsales, smartlead+getsales)
- status (lead, contacted, replied, qualified)
- phone, linkedin_url, location, notes

## Filtering by "Replied"

In the CRM UI:
1. Click the **Status** dropdown
2. Select **"replied"**
3. See only contacts who have replied

## Import from CSV

You can also import contacts from CSV:

1. Go to http://localhost:5173/contacts
2. Click "Import" button
3. Upload CSV with columns: email, first_name, last_name, company, etc.
4. Contacts are automatically deduplicated by email

## Sync Frequency

Run the sync script whenever you want to update:

```bash
# Manual sync
cd scripts && ./sync_crm.sh

# Or set up a cron job (every hour)
0 * * * * cd /path/to/magnum-opus/scripts && ./sync_crm.sh >> sync.log 2>&1
```

## Troubleshooting

### No contacts imported

Check if emails are present:
```bash
cd scripts
cat smartlead_contacts.json | grep -o '"email":[^,]*' | head -10
cat getsales_contacts.json | grep -o '"email":[^,]*' | head -10
```

### API errors

Check API keys are correct in `backend/.env`:
```bash
cat backend/.env | grep -E "SMARTLEAD|GETSALES"
```

### Backend not running

Start the backend:
```bash
./dev.sh
```

## Summary

**Result:** Unified CRM with contacts from both Smartlead and GetSales, with powerful filtering including "replied" status.

**Access:** http://localhost:5173/contacts

**Sync:** `cd scripts && ./sync_crm.sh`
