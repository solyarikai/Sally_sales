# Test Ground Truth — Valid References

This directory stores VERIFIED correct answers for test evaluation.

**CRITICAL RULE**: These files are used ONLY for COMPARING system output against reality.
They are NEVER injected into MCP prompts, never passed to the system, never used as hints.

## How evaluation works

```
1. System gets ONLY a URL (e.g. "https://easystaff.io/")
2. System scrapes, extracts, stores its understanding
3. Test agent reads the SYSTEM'S output
4. Test agent reads the GROUND TRUTH from this directory
5. Test agent COMPARES them and grades
6. If system got it wrong → log failure, fix, re-test
```

## Files

| File | What it validates |
|------|------------------|
| `offers/easystaff.json` | EasyStaff offer extraction from easystaff.io |
| `offers/thefashionpeople.json` | The Fashion People offer from thefashionpeople.com |
| `sequences/reference_3070919.json` | Reference sequence structure (Petr ES Australia) |
| `sequences/checklist.json` | GOD_SEQUENCE quality checklist (10 points) |
| `settings/reference_campaign.json` | Reference SmartLead campaign settings |

## Adding new ground truth

When testing a new company:
1. Manually scrape the website
2. Write the correct offer description
3. Save as `offers/{company}.json`
4. The test compares system's extraction against this file
