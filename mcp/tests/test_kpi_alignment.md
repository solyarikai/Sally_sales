# KPI Alignment — Math Specification & Test Cases

## Three KPIs

| Field | DB Column | Meaning | Default |
|-------|-----------|---------|---------|
| **target_people** | `target_people` | Total contacts to gather | 100 |
| **max_people_per_company** | `max_people_per_company` | Maximum contacts extracted per company | 3 |
| **target_companies** | `target_companies` | Target companies needed (DERIVED, optimistic) | ceil(100/3) = 34 |

## Core Formula (optimistic)

```
target_companies = ceil(target_people / max_people_per_company)
```

"Optimistic" = assumes every target company yields `max_people_per_company` contacts. In reality some yield fewer. But we calculate optimistically for KPI display.

## Alignment Rules

`target_people` and `max_people_per_company` are PRIMARY inputs.
`target_companies` is ALWAYS derived — EXCEPT when user explicitly sets it (then target_people adjusts).

## All Change Scenarios

### Scenario 1: User changes target_people only
```
Before: target_people=100, max_people_per_company=3, target_companies=34
User: "gather 200 contacts"
Action: target_people=200, max_people_per_company=3 (unchanged)
Result: target_companies = ceil(200/3) = 67
```

### Scenario 2: User changes max_people_per_company only
```
Before: target_people=100, max_people_per_company=3, target_companies=34
User: "set max 5 per company"
Action: max_people_per_company=5, target_people=100 (unchanged)
Result: target_companies = ceil(100/5) = 20
```

### Scenario 3: User changes target_companies only
```
Before: target_people=100, max_people_per_company=3, target_companies=34
User: "I need 50 target companies"
Action: target_companies=50, max_people_per_company=3 (unchanged)
Result: target_people = 50 * 3 = 150
```

### Scenario 4: User changes target_people AND max_people_per_company
```
Before: target_people=100, max_people_per_company=3, target_companies=34
User: "gather 500 contacts, 5 per company"
Action: target_people=500, max_people_per_company=5
Result: target_companies = ceil(500/5) = 100
```

### Scenario 5: User changes target_people AND target_companies
```
Before: target_people=100, max_people_per_company=3, target_companies=34
User: "I need 200 contacts from 40 companies"
Action: target_people=200, target_companies=40, max_people_per_company=unchanged=3
Result: Accept both. target_companies=40 is explicit. max_people_per_company stays 3.
Note: 40*3=120 < 200, so pipeline may need MORE than 40 companies. Show user: "40 companies x 3/company = 120 contacts (you asked for 200). Pipeline will gather until 200 contacts found."
```

### Scenario 6: User changes max_people_per_company AND target_companies
```
Before: target_people=100, max_people_per_company=3, target_companies=34
User: "5 per company, 30 target companies"
Action: max_people_per_company=5, target_companies=30
Result: target_people = 30 * 5 = 150
```

### Scenario 7: User changes all three
```
User: "gather 300 contacts from 60 companies, max 5 each"
Action: target_people=300, target_companies=60, max_people_per_company=5
Result: Accept all. 60*5=300, consistent. If inconsistent, use target_people as primary.
```

## Edge Cases

### Edge 1: max_people_per_company = 1
```
target_people=100, max=1 → target_companies=100
One contact per company. Many companies needed.
```

### Edge 2: Very large target
```
target_people=5000, max=3 → target_companies=1667
At 35% target rate from Apollo: 1667/0.35 = 4763 companies to search
At 25 per page: 191 Apollo pages = 191 credits
MCP MUST show this cost estimate before starting.
```

### Edge 3: target_people < max_people_per_company
```
target_people=2, max=3 → target_companies=1
Only 1 company needed, max 2 contacts from it.
```

### Edge 4: Pipeline mid-run, user increases target
```
Pipeline running: 67/100 contacts found, 23 target companies
User: "gather 200 contacts instead"
New: target_people=200, max=3, target_companies=ceil(200/3)=67
Remaining: 200-67=133 contacts needed
Pipeline continues from current page.
```

### Edge 5: Pipeline mid-run, user decreases max
```
Pipeline running: 45/100 contacts, max was 3
User: "max 1 per company"
New: max=1, target_people=100, target_companies=100
Contacts already gathered (45) don't change. Future extractions use max=1.
Need many more companies now.
```

## Implementation: `recalculate_kpis()` Function

```python
def recalculate_kpis(
    target_people: int | None,
    target_companies: int | None,
    max_people_per_company: int | None,
    # Which fields the user explicitly set in THIS call
    user_set: set[str],
) -> dict:
    """Returns aligned {target_people, target_companies, max_people_per_company}."""
    tp = target_people or 100
    mpc = max_people_per_company or 3
    tc = target_companies

    if "target_companies" in user_set and "target_people" not in user_set:
        # Scenario 3 or 6: user set companies → derive people
        tp = tc * mpc
    else:
        # Scenarios 1, 2, 4, 7: derive companies from people
        tc = ceil(tp / mpc)

    return {"target_people": tp, "target_companies": tc, "max_people_per_company": mpc}
```

## Stop Condition

Pipeline stops when: `total_people_found >= target_people`

`target_companies` is for DISPLAY and cost estimation only — not a stop condition.
The pipeline gathers companies and extracts people. It stops when enough PEOPLE are found.
