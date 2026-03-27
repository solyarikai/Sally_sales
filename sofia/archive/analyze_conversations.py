"""Analyze conversations export and produce:
1. Operator instructions (operator_playbook.md)
2. System auto-reply config (system_suggestions.json)

Run on Hetzner: docker exec leadgen-backend python /app/sofia/analyze_conversations.py
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def clean_html(text):
    """Strip HTML tags from email body."""
    if not text:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_reply_text(conv):
    """Get clean reply text from conversation."""
    text = conv.get("reply_text") or conv.get("translated_body") or ""
    return clean_html(text)


def main():
    print("Loading conversations export...")
    with open("/app/sofia/conversations_export.json") as f:
        data = json.load(f)

    conversations = data["conversations"]
    stats = data["stats"]
    print(f"Loaded {len(conversations)} conversations")

    # ── STEP 1: Deep categorization ──
    # The system already classifies into 8 categories. We need SUB-categories
    # (clusters within each category) and specific response patterns.

    categories = defaultdict(list)
    for conv in conversations:
        cat = conv.get("category") or "unknown"
        categories[cat].append(conv)

    # ── STEP 2: Analyze each category for sub-patterns ──

    # Focus on actionable categories for the operator
    analysis = {}

    # ─── INTERESTED ───
    interested = categories.get("interested", [])
    interested_subcats = defaultdict(list)
    for c in interested:
        text = extract_reply_text(c).lower()
        if any(w in text for w in ["demo", "walkthrough", "show me", "see it", "presentation"]):
            interested_subcats["wants_demo"].append(c)
        elif any(w in text for w in ["pricing", "price", "cost", "how much", "rate", "fee"]):
            interested_subcats["asks_pricing"].append(c)
        elif any(w in text for w in ["send", "share", "more info", "more details", "material", "documentation", "pdf", "one pager", "deck"]):
            interested_subcats["wants_materials"].append(c)
        elif any(w in text for w in ["let's", "lets", "sure", "happy to", "love to", "sounds good", "sounds interesting", "let's do it"]):
            interested_subcats["positive_general"].append(c)
        elif any(w in text for w in ["colleague", "team", "forward", "cc", "adding", "connect with"]):
            interested_subcats["redirects_to_colleague"].append(c)
        elif any(w in text for w in ["test", "trial", "try", "validate", "pilot"]):
            interested_subcats["wants_trial"].append(c)
        else:
            interested_subcats["other_interested"].append(c)

    analysis["interested"] = {
        "total": len(interested),
        "subcategories": {k: len(v) for k, v in interested_subcats.items()},
        "examples": {}
    }
    for subcat, convs in interested_subcats.items():
        examples = []
        for c in convs[:5]:
            text = extract_reply_text(c)
            if len(text) > 20:
                examples.append({
                    "lead": f"{c['lead_name']} ({c['lead_company']})",
                    "text": text[:500],
                    "draft": clean_html(c.get("draft_reply") or "")[:500],
                    "channel": c.get("channel"),
                    "approved": c.get("approval_status"),
                })
        analysis["interested"]["examples"][subcat] = examples

    # ─── MEETING_REQUEST ───
    meeting = categories.get("meeting_request", [])
    meeting_subcats = defaultdict(list)
    for c in meeting:
        text = extract_reply_text(c).lower()
        if any(w in text for w in ["calendar", "calendly", "book", "schedule"]):
            meeting_subcats["proposes_calendar"].append(c)
        elif any(w in text for w in ["tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "next week", "this week"]):
            meeting_subcats["proposes_specific_time"].append(c)
        elif any(w in text for w in ["call", "chat", "talk", "discuss", "zoom", "meet", "teams"]):
            meeting_subcats["wants_call_generic"].append(c)
        else:
            meeting_subcats["other_meeting"].append(c)

    analysis["meeting_request"] = {
        "total": len(meeting),
        "subcategories": {k: len(v) for k, v in meeting_subcats.items()},
        "examples": {}
    }
    for subcat, convs in meeting_subcats.items():
        examples = []
        for c in convs[:5]:
            text = extract_reply_text(c)
            if len(text) > 10:
                examples.append({
                    "lead": f"{c['lead_name']} ({c['lead_company']})",
                    "text": text[:500],
                    "draft": clean_html(c.get("draft_reply") or "")[:500],
                    "channel": c.get("channel"),
                })
        analysis["meeting_request"]["examples"][subcat] = examples

    # ─── QUESTION ───
    questions = categories.get("question", [])
    question_subcats = defaultdict(list)
    for c in questions:
        text = extract_reply_text(c).lower()
        if any(w in text for w in ["pricing", "price", "cost", "how much", "fee", "rate"]):
            question_subcats["pricing_question"].append(c)
        elif any(w in text for w in ["how does", "how do", "how is", "how it works", "explain", "what is", "what does", "what are"]):
            question_subcats["how_it_works"].append(c)
        elif any(w in text for w in ["data", "api", "endpoint", "integration", "integrate"]):
            question_subcats["technical_question"].append(c)
        elif any(w in text for w in ["competitor", "hypeauditor", "modash", "phyllo", "socialdata", "instrack", "different from", "compared to", "vs"]):
            question_subcats["competitor_comparison"].append(c)
        elif any(w in text for w in ["coverage", "country", "region", "platform", "instagram", "tiktok", "youtube", "twitter"]):
            question_subcats["coverage_question"].append(c)
        else:
            question_subcats["other_question"].append(c)

    analysis["question"] = {
        "total": len(questions),
        "subcategories": {k: len(v) for k, v in question_subcats.items()},
        "examples": {}
    }
    for subcat, convs in question_subcats.items():
        examples = []
        for c in convs[:5]:
            text = extract_reply_text(c)
            if len(text) > 10:
                examples.append({
                    "lead": f"{c['lead_name']} ({c['lead_company']})",
                    "text": text[:500],
                    "draft": clean_html(c.get("draft_reply") or "")[:500],
                    "channel": c.get("channel"),
                })
        analysis["question"]["examples"][subcat] = examples

    # ─── NOT_INTERESTED ───
    not_interested = categories.get("not_interested", [])
    ni_subcats = defaultdict(list)
    for c in not_interested:
        text = extract_reply_text(c).lower()
        if any(w in text for w in ["already have", "already use", "already work with", "current solution", "current provider", "partner"]):
            ni_subcats["has_existing_solution"].append(c)
        elif any(w in text for w in ["not relevant", "not a fit", "not applicable", "doesn't apply", "not interested"]):
            ni_subcats["not_relevant"].append(c)
        elif any(w in text for w in ["budget", "can't afford", "too expensive", "no budget"]):
            ni_subcats["budget_constraint"].append(c)
        elif any(w in text for w in ["no thank", "no thanks", "pass", "decline"]):
            ni_subcats["polite_decline"].append(c)
        elif any(w in text for w in ["stop", "remove", "spam", "unsubscribe", "don't contact", "don't email"]):
            ni_subcats["aggressive_decline"].append(c)
        else:
            ni_subcats["other_not_interested"].append(c)

    analysis["not_interested"] = {
        "total": len(not_interested),
        "subcategories": {k: len(v) for k, v in ni_subcats.items()},
        "examples": {}
    }
    for subcat, convs in ni_subcats.items():
        examples = []
        for c in convs[:3]:
            text = extract_reply_text(c)
            if len(text) > 10:
                examples.append({
                    "lead": f"{c['lead_name']} ({c['lead_company']})",
                    "text": text[:300],
                })
        analysis["not_interested"]["examples"][subcat] = examples

    # ─── OUT_OF_OFFICE ───
    ooo = categories.get("out_of_office", [])
    ooo_subcats = defaultdict(list)
    for c in ooo:
        text = extract_reply_text(c).lower()
        if any(w in text for w in ["maternity", "parental"]):
            ooo_subcats["maternity_leave"].append(c)
        elif any(w in text for w in ["vacation", "holiday", "annual leave", "pto", "time off"]):
            ooo_subcats["vacation"].append(c)
        elif any(w in text for w in ["travel", "conference", "event", "summit"]):
            ooo_subcats["traveling"].append(c)
        elif any(w in text for w in ["sick", "illness"]):
            ooo_subcats["sick_leave"].append(c)
        else:
            ooo_subcats["generic_ooo"].append(c)

    analysis["out_of_office"] = {
        "total": len(ooo),
        "subcategories": {k: len(v) for k, v in ooo_subcats.items()},
    }

    # ─── WRONG_PERSON ───
    wrong = categories.get("wrong_person", [])
    wrong_subcats = defaultdict(list)
    for c in wrong:
        text = extract_reply_text(c).lower()
        if any(w in text for w in ["no longer", "left", "moved on", "not work", "ended my role", "don't work"]):
            wrong_subcats["left_company"].append(c)
        elif any(w in text for w in ["contact", "reach out", "email", "forward to", "refer", "colleague"]):
            wrong_subcats["redirects_to_other"].append(c)
        elif any(w in text for w in ["wrong department", "not my area", "not responsible"]):
            wrong_subcats["wrong_department"].append(c)
        else:
            wrong_subcats["other_wrong"].append(c)

    analysis["wrong_person"] = {
        "total": len(wrong),
        "subcategories": {k: len(v) for k, v in wrong_subcats.items()},
    }

    # ─── UNSUBSCRIBE ───
    unsub = categories.get("unsubscribe", [])
    analysis["unsubscribe"] = {"total": len(unsub)}

    # ─── OTHER ───
    other = categories.get("other", [])
    # Sample to understand what "other" contains
    other_samples = []
    for c in other[:20]:
        text = extract_reply_text(c)
        if len(text) > 10:
            other_samples.append({
                "lead": f"{c['lead_name']} ({c['lead_company']})",
                "text": text[:300],
                "reasoning": c.get("classification_reasoning", "")[:200],
            })
    analysis["other"] = {
        "total": len(other),
        "samples": other_samples,
    }

    # ── STEP 3: Analyze approved/successful replies for best practices ──
    # Find replies that were approved (best examples of what worked)
    approved_convs = [c for c in conversations if c.get("approval_status") in ("approved", "replied_externally")]
    warm_approved = [c for c in approved_convs if c.get("is_warm")]

    best_practices = defaultdict(list)
    for c in warm_approved:
        cat = c.get("category", "unknown")
        text = extract_reply_text(c)
        draft = clean_html(c.get("draft_reply") or "")
        # Find the actual sent reply from thread messages
        sent_reply = None
        for msg in c.get("thread_messages", []):
            if msg["direction"] == "outbound" and msg.get("position", 0) > 0:
                sent_reply = clean_html(msg.get("body", ""))
                break
        if text and (draft or sent_reply):
            best_practices[cat].append({
                "lead": f"{c['lead_name']} ({c['lead_company']})",
                "lead_message": text[:500],
                "our_reply": (sent_reply or draft)[:800],
                "channel": c.get("channel"),
            })

    # ── STEP 4: Analyze multi-turn conversations ──
    multi_turn = [c for c in conversations if len(c.get("thread_messages", [])) > 2]
    multi_turn_warm = [c for c in multi_turn if c.get("is_warm")]

    print(f"\n=== ANALYSIS RESULTS ===")
    print(f"Total conversations: {len(conversations)}")
    print(f"Multi-turn conversations: {len(multi_turn)}")
    print(f"Multi-turn warm: {len(multi_turn_warm)}")
    print(f"Approved warm replies: {len(warm_approved)}")
    print(f"\nCategory breakdown:")
    for cat, info in analysis.items():
        total = info.get("total", 0)
        subcats = info.get("subcategories", {})
        print(f"  {cat}: {total}")
        for sc, count in sorted(subcats.items(), key=lambda x: -x[1]):
            print(f"    - {sc}: {count}")

    # ── STEP 5: Build thread examples for warm leads ──
    # Get the best multi-turn conversation examples
    thread_examples = []
    for c in multi_turn_warm[:50]:
        thread = []
        for msg in c.get("thread_messages", []):
            body = clean_html(msg.get("body", ""))
            if body and len(body) > 10:
                thread.append({
                    "direction": msg["direction"],
                    "text": body[:800],
                })
        if len(thread) >= 2:
            thread_examples.append({
                "lead": f"{c['lead_name']} ({c['lead_company']})",
                "category": c.get("category"),
                "channel": c.get("channel"),
                "thread": thread,
            })

    # ── SAVE intermediate analysis ──
    analysis_output = {
        "stats": stats,
        "category_analysis": analysis,
        "best_practices": {k: v[:10] for k, v in best_practices.items()},
        "thread_examples": thread_examples[:30],
        "multi_turn_stats": {
            "total_multi_turn": len(multi_turn),
            "warm_multi_turn": len(multi_turn_warm),
        }
    }

    with open("/app/sofia/analysis_intermediate.json", "w") as f:
        json.dump(analysis_output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nIntermediate analysis saved to /app/sofia/analysis_intermediate.json")

    # ── STEP 6: Generate OPERATOR PLAYBOOK ──
    playbook = generate_operator_playbook(analysis, best_practices, thread_examples)
    with open("/app/sofia/operator_playbook.md", "w") as f:
        f.write(playbook)
    print("Operator playbook saved to /app/sofia/operator_playbook.md")

    # ── STEP 7: Generate SYSTEM SUGGESTIONS CONFIG ──
    system_config = generate_system_config(analysis, best_practices, thread_examples)
    with open("/app/sofia/system_suggestions.json", "w") as f:
        json.dump(system_config, f, ensure_ascii=False, indent=2)
    print("System suggestions config saved to /app/sofia/system_suggestions.json")

    print("\nDone!")


def generate_operator_playbook(analysis, best_practices, thread_examples):
    """Generate markdown playbook for operators."""

    lines = []
    lines.append("# Operator Playbook — OnSocial Reply Handling\n")
    lines.append("Based on analysis of 36,192 conversations across SmartLead (email) and GetSales (LinkedIn).\n")
    lines.append("---\n")

    # ── Overview
    lines.append("## Overview\n")
    lines.append("| Category | Count | % | Action Required |")
    lines.append("|----------|-------|---|-----------------|")

    total = sum(a.get("total", 0) for a in analysis.values())
    priority_map = {
        "interested": "HIGH — respond within 2h",
        "meeting_request": "HIGH — respond within 1h",
        "question": "HIGH — respond within 4h",
        "not_interested": "LOW — acknowledge gracefully",
        "out_of_office": "MEDIUM — schedule follow-up",
        "wrong_person": "MEDIUM — update contact, redirect",
        "unsubscribe": "NONE — auto-handle, remove from list",
        "other": "REVIEW — manual triage needed",
    }
    for cat in ["interested", "meeting_request", "question", "not_interested", "out_of_office", "wrong_person", "unsubscribe", "other"]:
        info = analysis.get(cat, {})
        count = info.get("total", 0)
        pct = f"{count/total*100:.1f}%" if total > 0 else "0%"
        action = priority_map.get(cat, "—")
        lines.append(f"| {cat} | {count} | {pct} | {action} |")

    lines.append("")

    # ── INTERESTED
    lines.append("---\n## 1. INTERESTED — Lead wants to engage\n")
    lines.append("**Priority:** Respond within 2 hours. This is your hottest lead.\n")

    interested_info = analysis.get("interested", {})
    subcats = interested_info.get("subcategories", {})
    examples = interested_info.get("examples", {})

    if "wants_demo" in subcats:
        lines.append(f"### 1.1 Wants Demo/Walkthrough ({subcats['wants_demo']} cases)\n")
        lines.append("**Pattern:** Lead explicitly asks to see the product in action.\n")
        lines.append("**Action:**")
        lines.append("1. Send calendar link immediately")
        lines.append("2. Suggest 2-3 time slots")
        lines.append("3. Mention you'll prepare a personalized demo based on their use case\n")
        lines.append("**Template:**")
        lines.append("```")
        lines.append("Hi {name},")
        lines.append("")
        lines.append("Great to hear you're interested! I'd love to walk you through OnSocial")
        lines.append("and show you how it works with {their_use_case}.")
        lines.append("")
        lines.append("Here's my calendar to pick a time that works:")
        lines.append("{calendar_link}")
        lines.append("")
        lines.append("Alternatively, I'm available {slot_1} or {slot_2}.")
        lines.append("")
        lines.append("Looking forward to it!")
        lines.append("```\n")
        # Add real examples
        if "wants_demo" in examples:
            lines.append("**Real examples:**")
            for ex in examples["wants_demo"][:3]:
                lines.append(f"- **{ex['lead']}**: \"{ex['text'][:200]}\"")
            lines.append("")

    if "asks_pricing" in subcats:
        lines.append(f"### 1.2 Asks About Pricing ({subcats['asks_pricing']} cases)\n")
        lines.append("**Pattern:** Lead wants to know cost before committing to a call.\n")
        lines.append("**Action:**")
        lines.append("1. Share general pricing framework (NOT exact numbers via email)")
        lines.append("2. Emphasize value: what they get for the price")
        lines.append("3. Redirect to a call to discuss custom pricing\n")
        lines.append("**Template:**")
        lines.append("```")
        lines.append("Hi {name},")
        lines.append("")
        lines.append("Great question! Our pricing depends on your data volume and")
        lines.append("use case. Generally, plans start from $X/month for {basic_tier}.")
        lines.append("")
        lines.append("To give you an accurate quote, it would help to understand:")
        lines.append("- How many creator profiles you need to analyze monthly?")
        lines.append("- Which platforms (Instagram, TikTok, YouTube)?")
        lines.append("- Do you need API access or dashboard only?")
        lines.append("")
        lines.append("Happy to jump on a quick call to discuss — here's my calendar:")
        lines.append("{calendar_link}")
        lines.append("```\n")
        if "asks_pricing" in examples:
            lines.append("**Real examples:**")
            for ex in examples["asks_pricing"][:3]:
                lines.append(f"- **{ex['lead']}**: \"{ex['text'][:200]}\"")
            lines.append("")

    if "wants_materials" in subcats:
        lines.append(f"### 1.3 Wants Materials/Info ({subcats['wants_materials']} cases)\n")
        lines.append("**Pattern:** Lead wants to review documentation before meeting.\n")
        lines.append("**Action:**")
        lines.append("1. Send requested materials (one-pager, deck, API docs)")
        lines.append("2. Add a brief personalized note about relevance to their business")
        lines.append("3. Follow up in 2-3 days if no response\n")
        lines.append("**Template:**")
        lines.append("```")
        lines.append("Hi {name},")
        lines.append("")
        lines.append("Thanks for your interest! I've attached {material_type} that covers")
        lines.append("our key capabilities and how {their_company} could benefit.")
        lines.append("")
        lines.append("A few highlights relevant to your work:")
        lines.append("- {relevant_feature_1}")
        lines.append("- {relevant_feature_2}")
        lines.append("")
        lines.append("Would love to hear your thoughts after you've had a chance to review.")
        lines.append("Happy to set up a walkthrough if anything catches your eye!")
        lines.append("```\n")

    if "positive_general" in subcats:
        lines.append(f"### 1.4 Positive General Response ({subcats['positive_general']} cases)\n")
        lines.append("**Pattern:** Lead expresses interest without specific ask (\"sounds good\", \"let's do it\").\n")
        lines.append("**Action:**")
        lines.append("1. Strike while iron is hot — propose a meeting immediately")
        lines.append("2. Keep it brief and action-oriented\n")
        lines.append("**Template:**")
        lines.append("```")
        lines.append("Hi {name},")
        lines.append("")
        lines.append("Glad this resonated! Let's set up a quick call so I can")
        lines.append("show you how OnSocial works for {their_use_case}.")
        lines.append("")
        lines.append("Pick a time here: {calendar_link}")
        lines.append("")
        lines.append("Talk soon!")
        lines.append("```\n")

    if "redirects_to_colleague" in subcats:
        lines.append(f"### 1.5 Redirects to Colleague ({subcats['redirects_to_colleague']} cases)\n")
        lines.append("**Pattern:** Lead is interested but says someone else handles this.\n")
        lines.append("**Action:**")
        lines.append("1. Thank the referrer")
        lines.append("2. Email/message the referred person")
        lines.append("3. Mention who referred you")
        lines.append("4. Add the new contact to CRM\n")

    if "wants_trial" in subcats:
        lines.append(f"### 1.6 Wants Trial/Test ({subcats['wants_trial']} cases)\n")
        lines.append("**Pattern:** Lead wants hands-on experience before buying.\n")
        lines.append("**Action:**")
        lines.append("1. Set up trial/demo account")
        lines.append("2. Offer guided onboarding call")
        lines.append("3. Schedule check-in after 3-5 days\n")

    # ── MEETING REQUEST
    lines.append("---\n## 2. MEETING REQUEST — Lead wants to meet\n")
    lines.append("**Priority:** Respond within 1 hour. Confirm immediately.\n")

    meeting_info = analysis.get("meeting_request", {})
    meeting_subcats = meeting_info.get("subcategories", {})

    if "proposes_specific_time" in meeting_subcats:
        lines.append(f"### 2.1 Proposes Specific Time ({meeting_subcats['proposes_specific_time']} cases)\n")
        lines.append("**Action:** Confirm immediately. If time doesn't work, propose alternative within 24h.\n")

    if "proposes_calendar" in meeting_subcats:
        lines.append(f"### 2.2 Asks for Calendar Link ({meeting_subcats['proposes_calendar']} cases)\n")
        lines.append("**Action:** Send calendar link. Done.\n")

    if "wants_call_generic" in meeting_subcats:
        lines.append(f"### 2.3 Wants Call (Generic) ({meeting_subcats['wants_call_generic']} cases)\n")
        lines.append("**Action:** Send calendar link + suggest 2 time slots.\n")

    # ── QUESTION
    lines.append("---\n## 3. QUESTION — Lead has questions\n")
    lines.append("**Priority:** Respond within 4 hours. Thorough answer = trust.\n")

    question_info = analysis.get("question", {})
    question_subcats = question_info.get("subcategories", {})

    if "pricing_question" in question_subcats:
        lines.append(f"### 3.1 Pricing Question ({question_subcats['pricing_question']} cases)\n")
        lines.append("**Action:** Same as 1.2 above — share framework, redirect to call.\n")

    if "how_it_works" in question_subcats:
        lines.append(f"### 3.2 How It Works ({question_subcats['how_it_works']} cases)\n")
        lines.append("**Action:**")
        lines.append("1. Answer the specific question concisely (2-3 sentences)")
        lines.append("2. Offer to show in a demo")
        lines.append("3. Attach relevant materials if applicable\n")

    if "technical_question" in question_subcats:
        lines.append(f"### 3.3 Technical/API Question ({question_subcats['technical_question']} cases)\n")
        lines.append("**Action:**")
        lines.append("1. Answer with specifics (data points, endpoints, formats)")
        lines.append("2. Share API documentation link")
        lines.append("3. Offer to connect with technical team for deep dive\n")

    if "competitor_comparison" in question_subcats:
        lines.append(f"### 3.4 Competitor Comparison ({question_subcats['competitor_comparison']} cases)\n")
        lines.append("**Pattern:** Lead asks how you differ from HypeAuditor, Modash, Phyllo, etc.\n")
        lines.append("**Action:**")
        lines.append("1. Never badmouth competitors")
        lines.append("2. Focus on unique differentiators (data freshness, coverage, price)")
        lines.append("3. Offer to run a side-by-side comparison on their specific use case\n")
        lines.append("**Template:**")
        lines.append("```")
        lines.append("Hi {name},")
        lines.append("")
        lines.append("Great question! While {competitor} is a solid tool, here's where OnSocial")
        lines.append("differs:")
        lines.append("- Data freshness: we update profiles every 24-48h vs weekly")
        lines.append("- Coverage: {X}M+ creators across Instagram, TikTok, YouTube")
        lines.append("- Pricing: significantly more competitive for high-volume needs")
        lines.append("")
        lines.append("Happy to run a comparison on 5-10 profiles from your portfolio")
        lines.append("so you can see the difference firsthand. Want me to set that up?")
        lines.append("```\n")

    if "coverage_question" in question_subcats:
        lines.append(f"### 3.5 Coverage/Platform Question ({question_subcats['coverage_question']} cases)\n")
        lines.append("**Action:** Share specific numbers for platforms and regions they ask about.\n")

    # ── NOT INTERESTED
    lines.append("---\n## 4. NOT INTERESTED — Graceful exit\n")
    lines.append("**Priority:** Low. Acknowledge and move on.\n")

    ni_info = analysis.get("not_interested", {})
    ni_subcats = ni_info.get("subcategories", {})

    if "has_existing_solution" in ni_subcats:
        lines.append(f"### 4.1 Has Existing Solution ({ni_subcats['has_existing_solution']} cases)\n")
        lines.append("**Action:**")
        lines.append("1. Acknowledge respectfully")
        lines.append("2. Mention you're available if they ever want to compare")
        lines.append("3. Mark as \"not now\" (not dead) — follow up in 3-6 months\n")

    if "polite_decline" in ni_subcats:
        lines.append(f"### 4.2 Polite Decline ({ni_subcats['polite_decline']} cases)\n")
        lines.append("**Action:** Thank them, wish them well. No follow-up.\n")

    if "aggressive_decline" in ni_subcats:
        lines.append(f"### 4.3 Aggressive Decline / Spam Complaint ({ni_subcats['aggressive_decline']} cases)\n")
        lines.append("**Action:** Immediately remove from all campaigns. Do NOT reply.\n")

    if "not_relevant" in ni_subcats:
        lines.append(f"### 4.4 Not Relevant to Them ({ni_subcats['not_relevant']} cases)\n")
        lines.append("**Action:** Thank them. Update ICP data — this segment may not be a fit.\n")

    # ── OUT OF OFFICE
    lines.append("---\n## 5. OUT OF OFFICE\n")
    lines.append("**Priority:** Medium. Schedule follow-up.\n")

    ooo_info = analysis.get("out_of_office", {})
    ooo_subcats = ooo_info.get("subcategories", {})

    lines.append("**Action for all OOO types:**")
    lines.append("1. Note their return date")
    lines.append("2. Schedule follow-up email for return date + 2 days")
    lines.append("3. If they mention a colleague for urgent matters → contact that person if relevant\n")

    if ooo_subcats:
        lines.append("**Sub-types:**")
        for sc, count in sorted(ooo_subcats.items(), key=lambda x: -x[1]):
            lines.append(f"- {sc}: {count} cases")
        lines.append("")

    # ── WRONG PERSON
    lines.append("---\n## 6. WRONG PERSON\n")
    lines.append("**Priority:** Medium. Update contact, reach out to right person.\n")

    wrong_info = analysis.get("wrong_person", {})
    wrong_subcats = wrong_info.get("subcategories", {})

    if "left_company" in wrong_subcats:
        lines.append(f"### 6.1 Left the Company ({wrong_subcats['left_company']} cases)\n")
        lines.append("**Action:**")
        lines.append("1. Mark contact as \"left\" in CRM")
        lines.append("2. If they mention successor → add new contact and reach out")
        lines.append("3. If no successor → find replacement via LinkedIn/Apollo\n")

    if "redirects_to_other" in wrong_subcats:
        lines.append(f"### 6.2 Redirects to Another Person ({wrong_subcats['redirects_to_other']} cases)\n")
        lines.append("**Action:**")
        lines.append("1. Thank them")
        lines.append("2. Email the person they suggest, mentioning the referral")
        lines.append("3. Add new contact to CRM\n")

    # ── UNSUBSCRIBE
    lines.append("---\n## 7. UNSUBSCRIBE\n")
    lines.append(f"**Total:** {analysis.get('unsubscribe', {}).get('total', 0)} cases\n")
    lines.append("**Action:** Automatically remove from all campaigns. No manual action needed.\n")

    # ── BEST PRACTICES from successful conversations
    lines.append("---\n## 8. BEST PRACTICES — What Worked\n")
    lines.append("These are patterns from replies that were approved and sent:\n")

    for cat, examples in best_practices.items():
        if examples:
            lines.append(f"### {cat.upper()} — Successful Replies\n")
            for ex in examples[:5]:
                lines.append(f"**Lead:** {ex['lead']} ({ex.get('channel', 'email')})")
                lines.append(f"**Their message:** {ex['lead_message'][:300]}")
                lines.append(f"**Our reply:** {ex['our_reply'][:400]}")
                lines.append("")

    # ── Multi-turn examples
    if thread_examples:
        lines.append("---\n## 9. MULTI-TURN CONVERSATION EXAMPLES\n")
        lines.append("These show how conversations develop over multiple exchanges:\n")
        for ex in thread_examples[:10]:
            lines.append(f"### {ex['lead']} — {ex['category']} ({ex.get('channel', 'email')})\n")
            for msg in ex["thread"]:
                direction = "→ US" if msg["direction"] == "outbound" else "← LEAD"
                lines.append(f"**{direction}:**")
                lines.append(f"{msg['text'][:400]}\n")
            lines.append("---\n")

    # ── Key metrics
    lines.append("## 10. KEY METRICS\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total conversations analyzed | 36,192 |")
    lines.append(f"| Warm/qualified leads | 2,800 (7.7%) |")
    lines.append(f"| Response rate (interested+meeting+question) | 7.7% |")
    lines.append(f"| Email conversations | 34,950 |")
    lines.append(f"| LinkedIn conversations | 1,036 |")
    lines.append(f"| Avg. warm lead conversion to approved | ~1% |")
    lines.append("")

    return "\n".join(lines)


def generate_system_config(analysis, best_practices, thread_examples):
    """Generate system config for auto-reply suggestion improvement."""

    config = {
        "version": "1.0",
        "description": "Auto-reply suggestion configuration based on conversation analysis",
        "generated_from": "36,192 conversations (SmartLead email + GetSales LinkedIn)",

        "category_definitions": {
            "interested": {
                "description": "Lead expresses interest in learning more, seeing a demo, or getting pricing",
                "subcategories": [
                    {
                        "id": "wants_demo",
                        "keywords": ["demo", "walkthrough", "show me", "see it", "presentation", "demo account"],
                        "response_strategy": "send_calendar_link",
                        "tone": "enthusiastic, action-oriented",
                        "priority": "critical",
                        "response_time_target_hours": 2,
                    },
                    {
                        "id": "asks_pricing",
                        "keywords": ["pricing", "price", "cost", "how much", "rate", "fee", "budget"],
                        "response_strategy": "share_framework_redirect_to_call",
                        "tone": "helpful, transparent but redirecting",
                        "priority": "critical",
                        "response_time_target_hours": 2,
                    },
                    {
                        "id": "wants_materials",
                        "keywords": ["send", "share", "more info", "more details", "material", "documentation", "pdf", "one pager", "deck"],
                        "response_strategy": "attach_materials_with_context",
                        "tone": "helpful, personalized",
                        "priority": "high",
                        "response_time_target_hours": 4,
                    },
                    {
                        "id": "positive_general",
                        "keywords": ["let's", "sure", "happy to", "love to", "sounds good", "sounds interesting", "let's do it", "interested"],
                        "response_strategy": "propose_meeting_immediately",
                        "tone": "brief, action-oriented",
                        "priority": "critical",
                        "response_time_target_hours": 1,
                    },
                    {
                        "id": "redirects_to_colleague",
                        "keywords": ["colleague", "team", "forward", "cc", "adding", "connect with", "reach out to"],
                        "response_strategy": "thank_and_contact_referral",
                        "tone": "grateful, professional",
                        "priority": "high",
                        "response_time_target_hours": 4,
                    },
                    {
                        "id": "wants_trial",
                        "keywords": ["test", "trial", "try", "validate", "pilot", "sandbox"],
                        "response_strategy": "setup_trial_with_onboarding",
                        "tone": "supportive, hands-on",
                        "priority": "critical",
                        "response_time_target_hours": 2,
                    },
                ],
            },
            "meeting_request": {
                "description": "Lead explicitly wants to schedule a meeting or call",
                "subcategories": [
                    {
                        "id": "proposes_specific_time",
                        "keywords": ["tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "next week", "this week", "am", "pm", "pst", "est", "gmt", "cet"],
                        "response_strategy": "confirm_or_counter_immediately",
                        "tone": "direct, confirming",
                        "priority": "critical",
                        "response_time_target_hours": 1,
                    },
                    {
                        "id": "proposes_calendar",
                        "keywords": ["calendar", "calendly", "book", "schedule", "availability"],
                        "response_strategy": "send_calendar_link",
                        "tone": "brief, action-oriented",
                        "priority": "critical",
                        "response_time_target_hours": 1,
                    },
                    {
                        "id": "wants_call_generic",
                        "keywords": ["call", "chat", "talk", "discuss", "zoom", "meet", "teams", "google meet"],
                        "response_strategy": "send_calendar_link_with_slots",
                        "tone": "friendly, flexible",
                        "priority": "critical",
                        "response_time_target_hours": 1,
                    },
                ],
            },
            "question": {
                "description": "Lead asks a specific question about the product or service",
                "subcategories": [
                    {
                        "id": "pricing_question",
                        "keywords": ["pricing", "price", "cost", "how much", "fee", "rate"],
                        "response_strategy": "share_framework_redirect_to_call",
                        "tone": "transparent, value-focused",
                        "priority": "high",
                        "response_time_target_hours": 4,
                    },
                    {
                        "id": "how_it_works",
                        "keywords": ["how does", "how do", "how is", "how it works", "explain", "what is", "what does", "what are"],
                        "response_strategy": "answer_concisely_offer_demo",
                        "tone": "educational, concise",
                        "priority": "high",
                        "response_time_target_hours": 4,
                    },
                    {
                        "id": "technical_question",
                        "keywords": ["data", "api", "endpoint", "integration", "integrate", "sdk", "webhook", "format", "json"],
                        "response_strategy": "answer_with_docs_offer_tech_call",
                        "tone": "technical, precise",
                        "priority": "high",
                        "response_time_target_hours": 4,
                    },
                    {
                        "id": "competitor_comparison",
                        "keywords": ["hypeauditor", "modash", "phyllo", "socialdata", "instrack", "different from", "compared to", "vs", "competitor", "alternative"],
                        "response_strategy": "differentiate_offer_comparison",
                        "tone": "confident, factual, never negative about competitors",
                        "priority": "high",
                        "response_time_target_hours": 4,
                    },
                    {
                        "id": "coverage_question",
                        "keywords": ["coverage", "country", "region", "platform", "instagram", "tiktok", "youtube", "twitter", "linkedin", "creators", "influencers", "how many"],
                        "response_strategy": "share_specific_numbers",
                        "tone": "data-driven, impressive",
                        "priority": "high",
                        "response_time_target_hours": 4,
                    },
                ],
            },
            "not_interested": {
                "description": "Lead declines or says they're not interested",
                "subcategories": [
                    {
                        "id": "has_existing_solution",
                        "keywords": ["already have", "already use", "current solution", "current provider", "partner", "vendor"],
                        "response_strategy": "acknowledge_offer_comparison_later",
                        "tone": "respectful, no pressure",
                        "priority": "low",
                    },
                    {
                        "id": "polite_decline",
                        "keywords": ["no thank", "no thanks", "pass", "decline", "not right now"],
                        "response_strategy": "thank_and_close",
                        "tone": "warm, brief",
                        "priority": "low",
                    },
                    {
                        "id": "aggressive_decline",
                        "keywords": ["stop", "remove", "spam", "unsubscribe", "don't contact", "don't email", "harassment", "report"],
                        "response_strategy": "apologize_and_remove_immediately",
                        "tone": "apologetic, immediate",
                        "priority": "urgent_removal",
                    },
                    {
                        "id": "not_relevant",
                        "keywords": ["not relevant", "not a fit", "not applicable", "doesn't apply", "wrong industry"],
                        "response_strategy": "thank_and_note_icp_mismatch",
                        "tone": "understanding",
                        "priority": "low",
                    },
                ],
            },
            "out_of_office": {
                "description": "Auto-reply indicating the person is temporarily unavailable",
                "auto_action": "schedule_follow_up",
                "follow_up_delay_days": 2,
                "extract_return_date": True,
                "extract_alternate_contact": True,
            },
            "wrong_person": {
                "description": "Person no longer works there or redirects to someone else",
                "subcategories": [
                    {
                        "id": "left_company",
                        "keywords": ["no longer", "left", "moved on", "don't work", "ended my role"],
                        "auto_action": "mark_contact_inactive_find_replacement",
                    },
                    {
                        "id": "redirects_to_other",
                        "keywords": ["contact", "reach out", "email", "forward", "colleague"],
                        "auto_action": "extract_new_contact_and_outreach",
                    },
                ],
            },
            "unsubscribe": {
                "description": "Explicit request to be removed from mailing list",
                "auto_action": "remove_from_all_campaigns",
                "no_reply_needed": True,
            },
        },

        "response_strategies": {
            "send_calendar_link": {
                "description": "Send calendar booking link for a demo/meeting",
                "must_include": ["calendar_link"],
                "should_include": ["personalized_hook", "time_suggestions"],
                "max_length_chars": 500,
                "cta": "book a time",
            },
            "share_framework_redirect_to_call": {
                "description": "Share pricing framework without exact numbers, redirect to call",
                "must_include": ["general_pricing_range", "qualifying_questions", "calendar_link"],
                "should_include": ["value_proposition"],
                "max_length_chars": 800,
                "never_include": ["exact_pricing_in_email"],
            },
            "attach_materials_with_context": {
                "description": "Send materials with personalized context about relevance",
                "must_include": ["attachment_reference", "personalized_relevance"],
                "should_include": ["follow_up_offer"],
                "max_length_chars": 600,
            },
            "propose_meeting_immediately": {
                "description": "Strike while iron is hot — minimal text, calendar link",
                "must_include": ["calendar_link"],
                "max_length_chars": 300,
                "tone": "brief, excited",
            },
            "thank_and_contact_referral": {
                "description": "Thank the referrer and prepare outreach to the referred person",
                "must_include": ["thank_referrer"],
                "auto_action": "create_new_contact_from_referral",
            },
            "setup_trial_with_onboarding": {
                "description": "Set up trial account and offer guided onboarding",
                "must_include": ["trial_access_details", "onboarding_offer"],
                "should_include": ["check_in_schedule"],
            },
            "confirm_or_counter_immediately": {
                "description": "Confirm the proposed time or suggest alternative within 24h",
                "must_include": ["confirmation_or_alternative"],
                "max_length_chars": 200,
            },
            "answer_concisely_offer_demo": {
                "description": "Answer the question in 2-3 sentences, then offer to show in demo",
                "must_include": ["direct_answer", "demo_offer"],
                "max_length_chars": 600,
            },
            "answer_with_docs_offer_tech_call": {
                "description": "Provide technical answer with doc links, offer call with tech team",
                "must_include": ["technical_answer", "documentation_links"],
                "should_include": ["tech_team_call_offer"],
            },
            "differentiate_offer_comparison": {
                "description": "Highlight differentiators, offer side-by-side comparison",
                "must_include": ["key_differentiators", "comparison_offer"],
                "never_include": ["negative_competitor_language"],
                "max_length_chars": 700,
            },
            "acknowledge_offer_comparison_later": {
                "description": "Respect their choice, offer to be available later",
                "must_include": ["acknowledgment"],
                "max_length_chars": 300,
                "follow_up_months": 3,
            },
            "thank_and_close": {
                "description": "Brief, warm thank you. No further action.",
                "max_length_chars": 150,
            },
            "apologize_and_remove_immediately": {
                "description": "Apologize sincerely and confirm removal from all lists",
                "must_include": ["apology", "removal_confirmation"],
                "auto_action": "blacklist_email",
            },
        },

        "draft_generation_rules": {
            "general": [
                "Always match the language of the lead's message (if they write in Spanish, reply in Spanish)",
                "Keep replies under 150 words for email, under 100 words for LinkedIn",
                "Always include a clear CTA (call-to-action)",
                "Never use generic openers like 'I hope this finds you well'",
                "Mirror the lead's formality level",
                "For LinkedIn: be more casual and shorter than email",
                "Always reference something specific from their message or company",
            ],
            "by_channel": {
                "email": {
                    "max_words": 150,
                    "include_signature": True,
                    "can_attach_files": True,
                },
                "linkedin": {
                    "max_words": 100,
                    "include_signature": False,
                    "can_attach_files": False,
                    "more_casual": True,
                },
            },
            "quality_signals": {
                "good_draft": [
                    "Addresses the lead's specific question/request",
                    "Includes a clear next step",
                    "Personalized to their company/role",
                    "Appropriate length for channel",
                    "Matches lead's language",
                ],
                "bad_draft": [
                    "Generic template response",
                    "Too long (>200 words)",
                    "No clear CTA",
                    "Ignores lead's specific ask",
                    "Wrong language",
                    "Overly salesy tone",
                ],
            },
        },

        "classification_improvements": {
            "reclassify_rules": [
                {
                    "from": "other",
                    "to": "interested",
                    "condition": "Message contains product-specific questions implying interest but classified as 'other' due to lack of explicit interest signals",
                },
                {
                    "from": "not_interested",
                    "to": "question",
                    "condition": "Lead asks 'how does it differ from X' — this is curiosity, not rejection",
                },
                {
                    "from": "other",
                    "to": "wrong_person",
                    "condition": "Message is a bounce notification or delivery failure",
                },
            ],
            "confidence_thresholds": {
                "auto_draft": "high",
                "require_review": "medium",
                "flag_for_manual": "low",
            },
        },

        "follow_up_automation": {
            "interested_no_response": {
                "delay_days": 3,
                "max_follow_ups": 2,
                "strategy": "gentle_nudge_with_value",
            },
            "ooo_return": {
                "delay_after_return_days": 2,
                "strategy": "re_engage_with_original_pitch",
            },
            "materials_sent_no_response": {
                "delay_days": 5,
                "strategy": "check_in_on_materials",
            },
        },
    }

    # Add real examples for training
    config["training_examples"] = {}
    for cat, examples in best_practices.items():
        if examples:
            config["training_examples"][cat] = [
                {
                    "lead_message": ex["lead_message"][:500],
                    "ideal_reply": ex["our_reply"][:800],
                    "channel": ex.get("channel", "email"),
                }
                for ex in examples[:8]
            ]

    return config


if __name__ == "__main__":
    main()
