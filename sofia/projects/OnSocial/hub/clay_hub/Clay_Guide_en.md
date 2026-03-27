# Clay Guide — How to Export Unlimited Prospects

> Recording date: February 23, 2026

## Key Idea

Clay allows you to export an unlimited number of prospects. The limit per single search is **5,000 records**, but through multiple searches you can load 10,000, 20,000, 50,000 — all into one table.

---

## 1. Finding Companies (Find Leads)

1. Click **Find Leads**
2. Choose: search by **companies** or by **people**
   - Companies usually work better — more custom filters (revenue, etc.)
   - People search works too, just fewer filters available
3. Set up filters (location, size, funding, etc.)

### Example

Goal: find founders of large businesses in the UAE.

- Set location — UAE
- Result: 938 companies (narrow filters) or 10,000 (broad filters)

---

## 2. Bypassing the 5,000 Record Limit

If results exceed 5,000:

1. **First search** — narrow filters to get ≤ 5,000 records
   - E.g., companies with revenue from X to Y
2. **Export** to a new table (creates a Workbook)
3. **Second search** — adjust filters to the next range
   - E.g., revenue from Y to Z
4. **Export to the same table** — select **Save to existing table**
5. Repeat until everything is exported

> Rename your Workbook immediately to stay organized. E.g.: "Dubai Companies"

**How to split into batches:**
- By revenue ranges
- By company size (employee count)
- By other filters that yield batches ≤ 5,000

---

## 3. Finding People (Find People)

After exporting companies, find people within them:

1. **Find People** from the companies table
2. Filters:
   - **Job title** — C-Suite (exclude managers, assistants)
   - **Location** — e.g., UAE
3. Export to a new table

If people > 5,000 — split by job titles and export in batches into the same table.

### Visualization

The **Overview** tab shows the entire pipeline:
- 2 company searches → 10,000 companies
- CEO search → results in people table

---

## 4. Enrichment

### Email via FindyMail

1. Add enrichment → **FindyMail**
2. Select **Find work email**
3. Click **Continue** → **Run**

> **Important:** Use your own API key to avoid spending shared Clay credits.

### AI Enrichment

1. Add AI enrichment
2. Connect your own API key (ask Amir — he'll provide one with a limit)
3. Choose a model (GPT-4 or higher)
4. Write a prompt — same as in Crona

---

## 5. Key Rules

| Rule | Details |
|------|---------|
| Limit per search | 5,000 records |
| Bypassing the limit | Multiple searches → one table |
| API keys | Always use your own, not Clay credits |
| Expense tracking | Log API costs — otherwise you lose track |
| Naming | Rename Workbooks immediately |
| Delegation | Routine exports are best delegated to an assistant |
