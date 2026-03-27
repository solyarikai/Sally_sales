# Getsales to sheets automation

---

## Outcome

- Replies from your chosen **Getsales automations** will be appended/updated in your sheet

---

---

## Part 1 — n8n Setup

### 1) Create workflow from template

1. In n8n search **“Getsales reply example”** and duplicate it.

![image.png](Getsales%20to%20sheets%20automation/image.png)

1. You should see 3 nodes: **Webhook → Execution Data → Append or update row in sheet**.

> 💡 Tip: The template name may vary slightly. Choose the one that looks like the screenshots and contains a Google Sheets node.
> 
> 
> ![image.png](Getsales%20to%20sheets%20automation/image%201.png)
> 

### 2) Configure Google Sheets node

1. Open **Append or update row in sheet**.
2. **Operation:** `Append or Update Row`.
3. **Document:** select your Google Sheet.
4. **Sheet:** choose the exact tab to write into.
5. **Mapping Column Mode:** `Map Each Column Manually`.
6. **Column to match:** pick a unique key in your sheet (commonly `Linkedin`).

> 📌 After you change Document/Sheet, re-check mapping — n8n may clear fields.
> 

### 3) Map columns (Expressions only)

- Scroll to **Values to Send**.
- Ensure **every field is green** and marked as **Expression**.
- Example mappings (adjust to your sheet headers):

```
Linkedin (match): {{ $('Webhook').item.json.body.contact.linkedin_url }}
first_name:        {{ $('Webhook').item.json.body.contact.first_name }}
last_name:         {{ $('Webhook').item.json.body.contact.last_name }}
reply_text:        {{ $('Webhook').item.json.body.last_message.text }}
reply_datetime:    {{ $('Webhook').item.json.body.last_message.sent_at }}

```

> 🔎 How to find the right keys: click the Webhook node → Listen for test event, trigger a real reply in Getsales, and inspect the JSON payload in the right panel. Use the variable selector to insert safe paths.
> 

![image.png](Getsales%20to%20sheets%20automation/image%202.png)

### 4) Copy the Production Webhook URL

1. Open the **Webhook** node.
2. Switch to **Production URL** (not Test URL) and **copy** it.

![image.png](Getsales%20to%20sheets%20automation/image%203.png)

### 5) Save & activate later

- Click **Save** in n8n. We’ll activate after wiring Getsales.

---

## Part 2 — Getsales Webhook

### 6) Create a webhook in Getsales

1. **Name:** anything clear (e.g., `n8n – Replies to Sheet`).
2. **Event:** `Contact Replied` (or `Contact Replied LinkedIn Message`, depending on your workspace wording).
3. **Target URL:** paste the **Production URL** from n8n.

![image.png](Getsales%20to%20sheets%20automation/image%204.png)

![image.png](Getsales%20to%20sheets%20automation/image%205.png)

![image.png](Getsales%20to%20sheets%20automation/image%206.png)

### 7) Add filters for your automations

1. Click **Add rule** twice.
2. In the rule group header, set **OR** (blue).
3. For each rule:
    - **Select field:** `Automation`
    - **Operator:** `==`
    - **Value:** choose your automation from the dropdown
4. Repeat for **every** automation from which you want to collect replies.

### 8) Single-automation safety check

- If you only have **one** rule, confirm the **Not** toggle is **white** (disabled).

![image.png](Getsales%20to%20sheets%20automation/image%207.png)

### 9) Create

- Click **Create** (or **Save** if editing). Your webhook is live in Getsales.

---

## Part 3 — Go Live & Test

### 10) Activate the n8n workflow

- In n8n, **Activate** the workflow.

### Test flow

1. Send yourself a message from one of the selected automations and **reply**.
2. In n8n, check **Executions** → the run should be **Success**.
3. Open your Google Sheet → verify a new row is appended or an existing row is updated by the **match column**.

---

## Field & Sheet Tips

- **Match column** must exist in the sheet and match the value you send (e.g., full LinkedIn URL). If mismatched, rows will always append.
- Keep header names stable. Renaming columns in the sheet requires remapping in n8n.
- Use ISO timestamps for easier filtering/sorting (e.g., `2025-08-22T13:45:00Z`).

---