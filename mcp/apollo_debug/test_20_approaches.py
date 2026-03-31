"""Test 20 prompt approaches × 5 models for NL → Apollo filter mapping."""
import asyncio, json, httpx
from datetime import datetime

SEGMENTS = [
    {"query": "IT consulting companies in Miami", "label": "it_miami"},
    {"query": "Video production companies in London", "label": "video_london"},
    {"query": "Fashion brands in Italy", "label": "fashion_italy"},
    {"query": "Social media Influencer agencies in UK", "label": "influencer_agencies_uk"},
    {"query": "Social media Influencer platforms in UK", "label": "influencer_platforms_uk"},
]

GROUND_TRUTH = {
    "it_miami": {"good_ind": ["information technology & services", "management consulting"], "bad_ind": ["computer software", "computer networking", "internet"], "good_kw": ["it consulting", "it consulting services", "it consulting firm", "technology consulting", "managed it services"], "bad_kw": ["computer software", "computer networking", "internet"]},
    "video_london": {"good_ind": ["media production", "motion pictures & film", "broadcast media"], "bad_ind": ["information technology & services", "internet", "computer software"], "good_kw": ["video production", "media production", "film production", "content production"], "bad_kw": ["computer software", "internet", "information technology & services"]},
    "fashion_italy": {"good_ind": ["apparel & fashion", "luxury goods & jewelry"], "bad_ind": ["internet", "information technology & services"], "good_kw": ["italian fashion", "fashion brand italy", "luxury fashion italy", "made in italy fashion"], "bad_kw": ["internet", "computer software"]},
    "influencer_agencies_uk": {"good_ind": ["marketing & advertising"], "bad_ind": ["internet", "publishing", "information technology & services"], "good_kw": ["influencer marketing", "influencer marketing agency"], "bad_kw": ["internet", "publishing", "computer software"]},
    "influencer_platforms_uk": {"good_ind": ["marketing & advertising", "online media"], "bad_ind": ["internet", "publishing", "information technology & services"], "good_kw": ["influencer platforms", "influencer marketing platforms", "creator platforms"], "bad_kw": ["internet", "publishing", "computer software"]},
}

IND_PROMPTS = {
    "p1_score": 'Search: "{query}". Score each industry 0-100: "% of companies matching my search". Return 60+.\n{industries}\nJSON: {{"industries": [{{"name":"...","score":85}}]}}',
    "p2_yesno": 'Would "{query}" companies be listed under this industry? YES/NO each.\n{industries}\nJSON: {{"industries":["YES ones only"]}}',
    "p3_via_negativa": 'For "{query}": eliminate wrong industries first, then pick 2-4 best from remainder.\n{industries}\nJSON: {{"selected":["best ones"]}}',
    "p4_self_label": 'You run a {query} company. Which 2-3 Apollo industries is YOUR company listed under?\n{industries}\nJSON: {{"industries":["name"]}}',
    "p5_filter_test": 'If I filter Apollo by each industry for "{query}" — which 2-3 give most relevant, least noise?\n{industries}\nJSON: {{"industries":["name"]}}',
    "p6_minimal": '"{query}" — 2-3 matching industries.\n{industries}\nJSON: {{"industries":["name"]}}',
    "p7_precision": 'Pick industries where >50% of companies genuinely do "{query}". Max 3.\n{industries}\nJSON: {{"industries":["name"]}}',
    "p8_ranking": 'Rank by relevance to "{query}". Top 3 only.\n{industries}\nJSON: {{"industries":["name"]}}',
    "p9_exclusion_light": 'For "{query}" pick 2-4 most relevant industries. Skip any that are too generic.\n{industries}\nJSON: {{"industries":["name"]}}',
    "p10_one_shot": 'Apollo industry for "{query}"? Single BEST, then up to 2 more if clearly relevant.\n{industries}\nJSON: {{"industries":["name"]}}',
}

KW_PROMPTS = {
    "k1_score": 'Score 0-100 for "{query}": "Filtering Apollo by ONLY this keyword — % relevant?". Pick 50+.\n{keywords}\nJSON: {{"keywords":[{{"term":"...","score":80}}]}}',
    "k2_via_negativa": 'For "{query}": remove broad/irrelevant keywords. Pick 5-8 most specific from rest.\n{keywords}\nJSON: {{"selected":["specific ones"]}}',
    "k3_self_label": 'You run a {query} company. Which 5-8 tags from this list are on YOUR Apollo profile?\n{keywords}\nJSON: {{"keywords":["term"]}}',
    "k4_filter_test": 'Filtering Apollo for "{query}" — which 5-8 keywords give best results, least noise?\n{keywords}\nJSON: {{"keywords":["term"]}}',
    "k5_minimal": '"{query}" — pick 5-8 best Apollo keywords.\n{keywords}\nJSON: {{"keywords":["term"]}}',
    "k6_specificity": 'Sort by specificity to "{query}". Generic=bad, specific=good. Top 7.\n{keywords}\nJSON: {{"keywords":["most specific first"]}}',
    "k7_would_click": 'Searching for "{query}" — company tagged with keyword — would you click? Pick 5-8 "definitely yes".\n{keywords}\nJSON: {{"keywords":["term"]}}',
    "k8_signal_noise": 'For "{query}": signal (relevant) or noise (irrelevant)? Keep high-signal only, 5-8.\n{keywords}\nJSON: {{"keywords":["term"]}}',
    "k9_negativa_strict": 'Cross out keywords NOT specifically describing "{query}" companies. Pick top 7 survivors.\n{keywords}\nJSON: {{"keywords":["term"]}}',
    "k10_two_q": 'Each keyword: (1) Would {query} company have this tag? (2) Would unrelated company also have it? Keep only YES+NO pairs. Max 8.\n{keywords}\nJSON: {{"keywords":["term"]}}',
}

MODELS = ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "o4-mini"]

async def call_gpt(prompt, model, key, mt=500):
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": mt, "temperature": 0})
            data = resp.json()
            if "error" in data: return None, str(data.get("error",{}).get("message",""))[:80]
            ct = data["choices"][0]["message"]["content"].strip()
            if ct.startswith("```"): ct = ct.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(ct), None
    except json.JSONDecodeError: return None, "json_err"
    except Exception as e: return None, str(e)[:60]

def calc_score(label, inds, kws):
    gt = GROUND_TRUTH.get(label, {})
    gi, bi = set(x.lower() for x in gt.get("good_ind",[])), set(x.lower() for x in gt.get("bad_ind",[]))
    gk, bk = set(x.lower() for x in gt.get("good_kw",[])), set(x.lower() for x in gt.get("bad_kw",[]))
    ri, rk = set(x.lower() for x in inds), set(x.lower() for x in kws)
    return len(ri&gi) - 2*len(ri&bi) + len(rk&gk) - 2*len(rk&bk)

def extract(result, keys):
    if not result: return []
    for k in keys:
        v = result.get(k, [])
        if v:
            if isinstance(v[0], dict): return [x.get("name", x.get("term","")) for x in v if x.get("name") or x.get("term")]
            return [x for x in v if isinstance(x, str)]
    return []

async def main():
    from app.config import settings
    from app.db import async_session_maker
    from app.services.taxonomy_service import taxonomy_service as ts
    key = settings.OPENAI_API_KEY

    async with async_session_maker() as s:
        all_ind = await ts.get_all_industries(s)
        shortlists = {}
        for seg in SEGMENTS:
            shortlists[seg["label"]] = await ts.get_keyword_shortlist(seg["query"], key, s, top_n=50)

    ind_json = json.dumps(all_ind)
    all_results = []

    total = len(IND_PROMPTS) * len(MODELS) * len(SEGMENTS) + len(KW_PROMPTS) * len(MODELS) * len(SEGMENTS)
    done = 0

    print(f"Total API calls: {total}")
    print(f"\nINDUSTRY TESTS")
    for pname, tmpl in IND_PROMPTS.items():
        for model in MODELS:
            scores, details = [], []
            for seg in SEGMENTS:
                prompt = tmpl.format(query=seg["query"], industries=ind_json)
                result, err = await call_gpt(prompt, model, key, mt=400)
                done += 1
                if err:
                    details.append({"seg": seg["label"], "err": err}); continue
                inds = extract(result, ["industries", "selected", "include"])
                s = calc_score(seg["label"], inds, [])
                scores.append(s)
                details.append({"seg": seg["label"], "inds": inds, "score": s})
                await asyncio.sleep(0.1)
            avg = sum(scores)/len(scores) if scores else -99
            sym = "+" if avg >= 1.5 else "~" if avg >= 0 else "-"
            errs = sum(1 for d in details if "err" in d)
            print(f"  {sym} {pname:20s} {model:15s} avg={avg:+.1f} errs={errs} {[d.get('score','E') for d in details]}")
            all_results.append({"type":"ind","prompt":pname,"model":model,"avg":avg,"details":details})

    print(f"\nKEYWORD TESTS")
    for pname, tmpl in KW_PROMPTS.items():
        for model in MODELS:
            scores, details = [], []
            for seg in SEGMENTS:
                prompt = tmpl.format(query=seg["query"], keywords=json.dumps(shortlists[seg["label"]]))
                result, err = await call_gpt(prompt, model, key, mt=500)
                done += 1
                if err:
                    details.append({"seg": seg["label"], "err": err}); continue
                kws = extract(result, ["keywords", "selected"])
                s = calc_score(seg["label"], [], kws)
                scores.append(s)
                details.append({"seg": seg["label"], "kws": kws, "score": s})
                await asyncio.sleep(0.1)
            avg = sum(scores)/len(scores) if scores else -99
            sym = "+" if avg >= 2.0 else "~" if avg >= 0 else "-"
            errs = sum(1 for d in details if "err" in d)
            print(f"  {sym} {pname:20s} {model:15s} avg={avg:+.1f} errs={errs} {[d.get('score','E') for d in details]}")
            all_results.append({"type":"kw","prompt":pname,"model":model,"avg":avg,"details":details})

    # Leaderboards
    print(f"\n{'='*60}\nTOP 10 INDUSTRY\n{'='*60}")
    for r in sorted([x for x in all_results if x["type"]=="ind"], key=lambda x:-x["avg"])[:10]:
        print(f"  {r['avg']:+.1f}  {r['prompt']:20s} {r['model']}")

    print(f"\n{'='*60}\nTOP 10 KEYWORD\n{'='*60}")
    for r in sorted([x for x in all_results if x["type"]=="kw"], key=lambda x:-x["avg"])[:10]:
        print(f"  {r['avg']:+.1f}  {r['prompt']:20s} {r['model']}")

    # Best combo per segment
    print(f"\n{'='*60}\nBEST PER SEGMENT (industry + keyword combined)\n{'='*60}")
    for seg in SEGMENTS:
        best_ind = max([r for r in all_results if r["type"]=="ind"], key=lambda r: next((d["score"] for d in r["details"] if d.get("seg")==seg["label"] and "score" in d), -99))
        best_kw = max([r for r in all_results if r["type"]=="kw"], key=lambda r: next((d["score"] for d in r["details"] if d.get("seg")==seg["label"] and "score" in d), -99))
        bi = next((d for d in best_ind["details"] if d.get("seg")==seg["label"]), {})
        bk = next((d for d in best_kw["details"] if d.get("seg")==seg["label"]), {})
        print(f"\n  {seg['label']}:")
        print(f"    Best ind: {best_ind['prompt']} / {best_ind['model']} → {bi.get('inds',[])} (score={bi.get('score','?')})")
        print(f"    Best kw:  {best_kw['prompt']} / {best_kw['model']} → {bk.get('kws',[])} (score={bk.get('score','?')})")

    with open("/app/prompt_test_20.json", "w") as f:
        json.dump({"ts": datetime.now().isoformat(), "models": MODELS, "results": all_results}, f, indent=2, default=str)
    print(f"\nSaved {len(all_results)} results to /app/prompt_test_20.json")

asyncio.run(main())
