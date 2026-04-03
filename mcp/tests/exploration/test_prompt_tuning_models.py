"""Test different models for prompt tuning — find which model adjusts prompts best.

The prompt tuner has TWO GPT calls:
1. CLASSIFIER: classifies companies with the current prompt
2. IMPROVER: generates improved prompt based on mismatches

Test different models for EACH role independently.
Log everything to files.

Run:
    cd mcp && python3 -u tests/exploration/test_prompt_tuning_models.py
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

import httpx

_env = Path(__file__).parent.parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
CACHE_DIR = Path(__file__).parent.parent / "tmp" / "exploration_cache"
TMP_DIR = Path(__file__).parent.parent / "tmp"

# Agent verdicts = truth
VERDICTS = {
    "thenewgen.com": {"target": True, "reason": "Creator agency connecting brands with creators"},
    "sixteenth.com": {"target": True, "reason": "Influencer talent management"},
    "seenconnects.com": {"target": True, "reason": "Influencer & social marketing agency"},
    "found.co.uk": {"target": False, "reason": "Digital marketing agency (PPC/SEO), not influencer-focused"},
    "musetheagency.com": {"target": True, "reason": "Talent-first influencer marketing agency"},
    "unravelapp.com": {"target": False, "reason": "Travel booking app — unrelated"},
    "inthestyle.com": {"target": False, "reason": "Fashion retailer — no influencer marketing in website text"},
    "dexerto.media": {"target": False, "reason": "Gaming/pop culture media hub — not a buyer"},
    "majorplayers.co.uk": {"target": False, "reason": "Recruitment agency for creative roles — recruits, doesn't operate"},
    "lindafarrow.com": {"target": False, "reason": "Luxury eyewear brand — unrelated"},
}

QUERY = "Influencer marketing platforms and creator economy companies in UK"
OFFER = "OnSocial — AI-powered creator data solution for influencer marketing"

# Models to test for each role
CLASSIFIER_MODELS = ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1-nano"]
IMPROVER_MODELS = ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4o", "gpt-4.1-nano"]


def _build_initial_prompt():
    return f"""EXCLUDE companies that should NOT be contacted. Keep everything else.

WE SELL: {OFFER}
TARGET SEGMENT: {QUERY}

EXCLUDE ONLY IF one of these is true:
1. DIRECT COMPETITOR: sells the SAME type of product (same category, same buyer)
2. COMPLETELY UNRELATED: zero overlap with the target segment or its supply chain
3. WRONG GEOGRAPHY or WRONG INDUSTRY: explicitly outside the search criteria

INCLUDE if ANY of these is true:
- Company is an AGENCY that does work in the target segment
- Company is a PLATFORM that operates in the target space
- Company is a BRAND that actively engages in the activity our product supports
- Company manages TALENT/PEOPLE in the target space

A recruitment agency that places people in the industry is NOT a buyer (they recruit, not operate).
A general digital marketing agency (PPC/SEO) is NOT a buyer unless specifically in the target segment.
A media company covering the industry is NOT a buyer (they report, not operate).

Return JSON array:
[{{"domain": "...", "is_target": true/false, "segment": "CAPS_LABEL", "reasoning": "1 sentence"}}]

Companies:
"""


async def classify_batch(companies, prompt, model):
    full = prompt
    for c in companies:
        d = c["domain"]
        text = c.get("scraped_text", "")[:500]
        full += f"\n--- {d} ---\n{text}\n"

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": full}],
                      "max_tokens": 2000, "temperature": 0},
            )
            data = resp.json()
            if "error" in data:
                return {}, str(data["error"])[:100]
            content = data["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            cls = json.loads(content)
            return {c.get("domain", ""): {"is_target": c.get("is_target", False), "reasoning": c.get("reasoning", "")} for c in cls}, None
    except Exception as e:
        return {}, str(e)[:100]


def compare(gpt_results, verdicts):
    correct, total, mismatches = 0, 0, []
    for domain, v in verdicts.items():
        gpt = gpt_results.get(domain, {})
        total += 1
        if v["target"] == gpt.get("is_target", False):
            correct += 1
        else:
            mismatches.append({
                "domain": domain, "agent": v["target"], "gpt": gpt.get("is_target", False),
                "agent_reason": v["reason"], "gpt_reason": gpt.get("reasoning", ""),
            })
    return correct / total if total else 0, mismatches


async def improve_prompt(current, mismatches, model):
    mm_text = ""
    for m in mismatches:
        d = "should be TARGET but GPT said NOT" if m["agent"] else "should NOT be target but GPT said YES"
        mm_text += f"- {m['domain']}: {d}. Reason: {m['agent_reason']}\n"

    prompt = f"""Improve this classification prompt. It made these mistakes:
{mm_text}

Current prompt:
{current}

Generate an improved prompt that fixes these mismatches.
Do NOT include specific company names or domains.
Keep the via negativa approach.

Return ONLY the improved prompt text."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": 1000, "temperature": 0.3},
            )
            data = resp.json()
            if "error" in data:
                return current
            content = data["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            return content
    except Exception:
        return current


async def run_tuning(classifier_model, improver_model, companies, max_iter=5):
    """Run prompt tuning loop with specific models. Returns history."""
    prompt = _build_initial_prompt()
    history = []

    for i in range(max_iter):
        results, err = await classify_batch(companies, prompt, classifier_model)
        if err:
            history.append({"iter": i, "error": err})
            break

        acc, mismatches = compare(results, VERDICTS)
        history.append({
            "iter": i, "accuracy": acc,
            "mismatches": [{"domain": m["domain"], "type": "FP" if not m["agent"] else "FN"} for m in mismatches],
            "prompt_len": len(prompt),
        })

        if acc >= 0.95:
            break

        prompt = await improve_prompt(prompt, mismatches, improver_model)

    return history


async def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    lines = []

    def log(msg):
        print(msg)
        lines.append(msg)

    # Load companies
    companies = []
    for domain in VERDICTS:
        f = CACHE_DIR / f"scrape_{domain.replace('.', '_').replace('/', '_')}.json"
        if f.exists():
            data = json.loads(f.read_text())
            companies.append({"domain": domain, "scraped_text": data.get("text", "")[:3000]})

    if len(companies) < 8:
        log("ERROR: Need cached scrape data. Run test_e2e_real.py first.")
        return

    log(f"PROMPT TUNING MODEL TEST — {ts}")
    log(f"Segment: OnSocial Creator UK (the hardest case)")
    log(f"Companies: {len(companies)}")
    log(f"Classifier models: {CLASSIFIER_MODELS}")
    log(f"Improver models: {IMPROVER_MODELS}")
    log(f"Total setups: {len(CLASSIFIER_MODELS) * len(IMPROVER_MODELS)}")
    log("=" * 90)

    all_results = []

    for cls_model in CLASSIFIER_MODELS:
        for imp_model in IMPROVER_MODELS:
            setup = f"classify={cls_model} improve={imp_model}"
            log(f"\n--- {setup} ---")

            t0 = time.time()
            history = await run_tuning(cls_model, imp_model, companies)
            elapsed = time.time() - t0

            final = history[-1] if history else {}
            final_acc = final.get("accuracy", 0)
            iters = len(history)
            final_mismatches = final.get("mismatches", [])

            icon = "✅" if final_acc >= 0.95 else "⚠️" if final_acc >= 0.90 else "❌"
            log(f"  {icon} Final: {final_acc*100:.0f}% after {iters} iters ({elapsed:.0f}s)")

            # Show accuracy progression
            accs = [h.get("accuracy", 0) for h in history if "accuracy" in h]
            log(f"  Progression: {' → '.join(f'{a*100:.0f}%' for a in accs)}")

            if final_mismatches:
                log(f"  Remaining errors: {[m['domain'] for m in final_mismatches]}")

            all_results.append({
                "classifier": cls_model, "improver": imp_model,
                "final_accuracy": final_acc, "iterations": iters,
                "time": elapsed, "history": history,
                "remaining_errors": [m["domain"] for m in final_mismatches],
            })

    # Summary
    log(f"\n{'='*90}")
    log(f"{'Setup':<55} {'Acc':>6} {'Iters':>6} {'Time':>6} {'Errors'}")
    log("-" * 90)
    sorted_r = sorted(all_results, key=lambda x: (-x["final_accuracy"], x["iterations"]))
    for r in sorted_r:
        setup = f"cls={r['classifier']:<15} imp={r['improver']}"
        errs = ", ".join(r["remaining_errors"][:3]) if r["remaining_errors"] else "none"
        log(f"{setup:<55} {r['final_accuracy']*100:>5.0f}% {r['iterations']:>5} {r['time']:>5.0f}s  {errs}")

    best = sorted_r[0]
    log(f"\nBEST: cls={best['classifier']} imp={best['improver']} ({best['final_accuracy']*100:.0f}%, {best['iterations']} iters)")

    # Save
    log_file = TMP_DIR / f"{ts}_prompt_tuning_models.log"
    log_file.write_text("\n".join(lines))
    results_file = TMP_DIR / f"{ts}_prompt_tuning_models.json"
    results_file.write_text(json.dumps({
        "ts": ts, "results": all_results, "best": {
            "classifier": best["classifier"], "improver": best["improver"],
            "accuracy": best["final_accuracy"], "iterations": best["iterations"],
        },
    }, indent=2, default=str))
    log(f"\nSaved: {log_file.name}, {results_file.name}")


if __name__ == "__main__":
    asyncio.run(main())
