"""Test 20 prompt approaches × 5 models. Results saved incrementally to /app/apollo_debug/."""
import asyncio, json, httpx, os
from datetime import datetime

SEGMENTS = [
    {"query": "IT consulting companies in Miami", "label": "it_miami"},
    {"query": "Video production companies in London", "label": "video_london"},
    {"query": "Fashion brands in Italy", "label": "fashion_italy"},
    {"query": "Social media Influencer agencies in UK", "label": "influencer_agencies_uk"},
    {"query": "Social media Influencer platforms in UK", "label": "influencer_platforms_uk"},
]

GT = {
    "it_miami": {"gi": ["information technology & services", "management consulting"], "bi": ["computer software", "computer networking", "internet"], "gk": ["it consulting", "it consulting services", "it consulting firm", "technology consulting", "managed it services"], "bk": ["computer software", "computer networking", "internet"]},
    "video_london": {"gi": ["media production", "motion pictures & film", "broadcast media"], "bi": ["information technology & services", "internet", "computer software"], "gk": ["video production", "media production", "film production", "content production"], "bk": ["computer software", "internet", "information technology & services"]},
    "fashion_italy": {"gi": ["apparel & fashion", "luxury goods & jewelry"], "bi": ["internet", "information technology & services"], "gk": ["italian fashion", "fashion brand italy", "luxury fashion italy", "made in italy fashion"], "bk": ["internet", "computer software"]},
    "influencer_agencies_uk": {"gi": ["marketing & advertising"], "bi": ["internet", "publishing", "information technology & services"], "gk": ["influencer marketing", "influencer marketing agency"], "bk": ["internet", "publishing", "computer software"]},
    "influencer_platforms_uk": {"gi": ["marketing & advertising", "online media"], "bi": ["internet", "publishing", "information technology & services"], "gk": ["influencer platforms", "influencer marketing platforms", "creator platforms"], "bk": ["internet", "publishing", "computer software"]},
}

IND = {
    "p1_score": 'Search: "{q}". Score each 0-100: "% of companies matching". Return 60+.\n{i}\nJSON: {{"industries": [{{"name":"...","score":85}}]}}',
    "p2_yesno": 'Would "{q}" companies be listed under this industry? YES/NO.\n{i}\nJSON: {{"industries":["YES ones"]}}',
    "p3_via_negativa": 'For "{q}": eliminate wrong, pick 2-4 best from rest.\n{i}\nJSON: {{"selected":["best"]}}',
    "p4_self_label": 'You run a {q} company. Which 2-3 industries is YOUR company under?\n{i}\nJSON: {{"industries":["name"]}}',
    "p5_filter_test": 'Filter Apollo for "{q}" — which 2-3 industries give most relevant, least noise?\n{i}\nJSON: {{"industries":["name"]}}',
    "p6_minimal": '"{q}" — 2-3 matching industries.\n{i}\nJSON: {{"industries":["name"]}}',
    "p7_precision": 'Industries where >50% genuinely do "{q}". Max 3.\n{i}\nJSON: {{"industries":["name"]}}',
    "p8_ranking": 'Rank by relevance to "{q}". Top 3.\n{i}\nJSON: {{"industries":["name"]}}',
    "p9_skip_generic": '"{q}" — pick 2-4 most relevant. Skip generic.\n{i}\nJSON: {{"industries":["name"]}}',
    "p10_best_then_more": 'Single BEST industry for "{q}", then up to 2 more if clearly relevant.\n{i}\nJSON: {{"industries":["name"]}}',
}

KW = {
    "k1_score": 'Score 0-100 for "{q}": "Only this keyword — % relevant?". Pick 50+.\n{k}\nJSON: {{"keywords":[{{"term":"...","score":80}}]}}',
    "k2_via_negativa": '"{q}": remove broad/irrelevant. Pick 5-8 specific from rest.\n{k}\nJSON: {{"selected":["specific"]}}',
    "k3_self_label": 'You run a {q} company. Which 5-8 tags on YOUR profile?\n{k}\nJSON: {{"keywords":["term"]}}',
    "k4_filter_test": 'Filter Apollo for "{q}" — 5-8 keywords, best results least noise.\n{k}\nJSON: {{"keywords":["term"]}}',
    "k5_minimal": '"{q}" — 5-8 best keywords.\n{k}\nJSON: {{"keywords":["term"]}}',
    "k6_specificity": 'Sort by specificity to "{q}". Generic=bad. Top 7.\n{k}\nJSON: {{"keywords":["specific first"]}}',
    "k7_would_click": 'Searching "{q}" — tagged company — click? 5-8 "yes".\n{k}\nJSON: {{"keywords":["term"]}}',
    "k8_signal_noise": '"{q}": signal or noise? Keep high-signal, 5-8.\n{k}\nJSON: {{"keywords":["term"]}}',
    "k9_strict_negativa": 'Cross out NOT "{q}". Top 7 survivors.\n{k}\nJSON: {{"keywords":["term"]}}',
    "k10_two_q": 'Each: (1) {q} company has tag? (2) Unrelated also? Keep YES+NO only. Max 8.\n{k}\nJSON: {{"keywords":["term"]}}',
}

MODELS = ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "o4-mini"]
OUTDIR = "/app/apollo_debug"

async def gpt(prompt, model, key, mt=500):
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": mt, "temperature": 0})
            d = r.json()
            if "error" in d: return None, str(d.get("error",{}).get("message",""))[:80]
            ct = d["choices"][0]["message"]["content"].strip()
            if ct.startswith("```"): ct = ct.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(ct), None
    except json.JSONDecodeError: return None, "json_err"
    except Exception as e: return None, str(e)[:60]

def sc(label, inds, kws):
    g = GT.get(label, {})
    ri, rk = set(x.lower() for x in inds), set(x.lower() for x in kws)
    gi, bi = set(x.lower() for x in g.get("gi",[])), set(x.lower() for x in g.get("bi",[]))
    gk, bk = set(x.lower() for x in g.get("gk",[])), set(x.lower() for x in g.get("bk",[]))
    return len(ri&gi) - 2*len(ri&bi) + len(rk&gk) - 2*len(rk&bk)

def ex(result, keys):
    if not result: return []
    for k in keys:
        v = result.get(k, [])
        if v:
            if isinstance(v[0], dict): return [x.get("name", x.get("term","")) for x in v if x.get("name") or x.get("term")]
            return [x for x in v if isinstance(x, str)]
    return []

def save(name, data):
    os.makedirs(OUTDIR, exist_ok=True)
    path = f"{OUTDIR}/{name}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)

async def main():
    from app.config import settings
    from app.db import async_session_maker
    from app.services.taxonomy_service import taxonomy_service as ts
    key = settings.OPENAI_API_KEY

    async with async_session_maker() as s:
        all_ind = await ts.get_all_industries(s)
        sl = {}
        for seg in SEGMENTS:
            sl[seg["label"]] = await ts.get_keyword_shortlist(seg["query"], key, s, top_n=50)

    ij = json.dumps(all_ind)
    leaderboard = []

    # INDUSTRY TESTS
    for pname, tmpl in IND.items():
        for model in MODELS:
            scores, details = [], []
            for seg in SEGMENTS:
                result, err = await gpt(tmpl.format(q=seg["query"], i=ij), model, key, mt=400)
                if err: details.append({"seg": seg["label"], "err": err}); continue
                inds = ex(result, ["industries", "selected", "include"])
                s = sc(seg["label"], inds, [])
                scores.append(s)
                details.append({"seg": seg["label"], "inds": inds, "score": s})
                await asyncio.sleep(0.1)
            avg = sum(scores)/len(scores) if scores else -99
            errs = sum(1 for d in details if "err" in d)
            sym = "+" if avg >= 1.5 else "~" if avg >= 0 else "-"
            print(f"{sym} IND {pname:20s} {model:15s} avg={avg:+.1f} errs={errs} {[d.get('score','E') for d in details]}")
            entry = {"type":"ind","prompt":pname,"model":model,"avg":avg,"errs":errs,"details":details}
            leaderboard.append(entry)
            # Save each result immediately
            save(f"ind_{pname}_{model}", entry)

    # KEYWORD TESTS
    for pname, tmpl in KW.items():
        for model in MODELS:
            scores, details = [], []
            for seg in SEGMENTS:
                result, err = await gpt(tmpl.format(q=seg["query"], k=json.dumps(sl[seg["label"]])), model, key, mt=500)
                if err: details.append({"seg": seg["label"], "err": err}); continue
                kws = ex(result, ["keywords", "selected"])
                s = sc(seg["label"], [], kws)
                scores.append(s)
                details.append({"seg": seg["label"], "kws": kws, "score": s})
                await asyncio.sleep(0.1)
            avg = sum(scores)/len(scores) if scores else -99
            errs = sum(1 for d in details if "err" in d)
            sym = "+" if avg >= 2.0 else "~" if avg >= 0 else "-"
            print(f"{sym} KW  {pname:20s} {model:15s} avg={avg:+.1f} errs={errs} {[d.get('score','E') for d in details]}")
            entry = {"type":"kw","prompt":pname,"model":model,"avg":avg,"errs":errs,"details":details}
            leaderboard.append(entry)
            save(f"kw_{pname}_{model}", entry)

    # Leaderboards
    print(f"\nTOP 10 INDUSTRY")
    for r in sorted([x for x in leaderboard if x["type"]=="ind"], key=lambda x:-x["avg"])[:10]:
        print(f"  {r['avg']:+.1f}  {r['prompt']:20s} {r['model']}")
    print(f"\nTOP 10 KEYWORD")
    for r in sorted([x for x in leaderboard if x["type"]=="kw"], key=lambda x:-x["avg"])[:10]:
        print(f"  {r['avg']:+.1f}  {r['prompt']:20s} {r['model']}")

    # Best per segment
    print(f"\nBEST PER SEGMENT")
    for seg in SEGMENTS:
        bi = max([r for r in leaderboard if r["type"]=="ind"], key=lambda r: next((d["score"] for d in r["details"] if d.get("seg")==seg["label"] and "score" in d), -99))
        bk = max([r for r in leaderboard if r["type"]=="kw"], key=lambda r: next((d["score"] for d in r["details"] if d.get("seg")==seg["label"] and "score" in d), -99))
        bid = next((d for d in bi["details"] if d.get("seg")==seg["label"]), {})
        bkd = next((d for d in bk["details"] if d.get("seg")==seg["label"]), {})
        print(f"  {seg['label']}:")
        print(f"    IND: {bi['prompt']}/{bi['model']} → {bid.get('inds',[])} ({bid.get('score','?')})")
        print(f"    KW:  {bk['prompt']}/{bk['model']} → {bkd.get('kws',[])} ({bkd.get('score','?')})")

    save("leaderboard", {"ts": datetime.now().isoformat(), "results": leaderboard})

asyncio.run(main())
