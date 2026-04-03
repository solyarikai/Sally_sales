"""
Seed campaign_patterns table with real patterns extracted from EasyStaff Global campaigns.

These patterns are derived from:
- 55 warm/qualified leads analysis
- 3,500+ total replies across 30+ SmartLead campaigns
- 5-step sequence performance data (which step triggers which buyer type)
- Real conversation patterns from closed deals
- Keyword effectiveness tracking (53K companies, 7,919 targets)

Run on Hetzner:
  ssh hetzner "cd ~/magnum-opus-project/repo && docker exec leadgen-backend \
    python -m app.scripts.seed_campaign_patterns"
"""
import asyncio
import sys
sys.path.insert(0, "/app")

from app.db import async_session_maker
from app.models.campaign_intelligence import CampaignPattern

COMPANY_ID = 1

# Real patterns extracted from EasyStaff Global campaign data
PATTERNS = [
    # ===== SUBJECT LINES =====
    {
        "pattern_type": "subject_line",
        "pattern_key": "first_name_dash_pain_point",
        "title": "{{first_name}} – [pain point question]",
        "description": """Subject line format: "{{first_name}} – paying freelancers abroad?"

Why it works: Personal (first name), immediately relevant (pain point as question),
short enough for mobile preview. The en-dash (–) is visually distinctive vs hyphen.

Evidence: EasyStaff Global's top-performing subject across 170 campaigns.
Step 1 triggers 25% of all warm replies. Karen Scorrano replied in 40 minutes.
Muhammad Arshad replied in 50 minutes. Both from Step 1 with this subject format.

How to apply: "[Name] – [core pain as yes/no question]?"
Examples:
- "{{first_name}} – paying contractors in multiple countries?"
- "{{first_name}} – spending too much on Deel?"
- "{{first_name}} – managing remote team payments?"

DO NOT: Use generic subjects ("Quick question", "Following up"), clickbait,
or long subjects that get cut off on mobile.""",
        "market": None,  # universal
        "channel": "email",
        "confidence": 0.92,
    },

    # ===== BODY STRUCTURE =====
    {
        "pattern_type": "body_structure",
        "pattern_key": "four_paragraph_arc",
        "title": "4-paragraph arc: Hook → Value → Proof → CTA",
        "description": """Step 1 body structure that generates 25% of warm replies:

Paragraph 1 (Hook): One sentence stating what you do + key differentiator.
"We at [Company] help companies [solve X] with [key differentiator]."

Paragraph 2 (Capability): 1-2 sentences expanding on HOW, listing 2-3 specific methods.
"You can [method 1], [method 2], and [method 3] – all [handled/managed] by us."

Paragraph 3 (Proof): Specific case study with numbers. Geography-personalized.
"Recently helped a [{{city}}] [industry] switch from [Competitor] to [result],
saving them $X/month on [specific cost category]."

Paragraph 4 (CTA): Soft question, not a calendar link.
"Would you like to calculate the cost benefit for your case?"

Key metrics:
- Total length: 4-6 short paragraphs, under 150 words
- No bullet points in Step 1 (save for Step 2)
- Signature: Name, Title, Company, trust line ("Trusted by X+ teams")
- The proof paragraph with {{city}} personalization drives recognition""",
        "market": None,
        "channel": "email",
        "confidence": 0.88,
    },

    # ===== TIMING =====
    {
        "pattern_type": "timing",
        "pattern_key": "day_0_3_4_7_7",
        "title": "5-step cadence: Day 0 → 3 → 4 → 7 → 7",
        "description": """Optimal sequence timing proven across EasyStaff Global campaigns:

Step 1: Day 0 — Hook + value prop + proof + CTA (25% of warm replies)
Step 2: Day 3 — Competitor displacement + bullet points (31% of warm replies)
Step 3: Day 4 — Pricing transparency + video offer (14% of warm replies)
Step 4: Day 7 — Channel switch: "LinkedIn or Telegram?" + "Sent from iPhone" (31% of warm replies)
Step 5: Day 7 — Final: acknowledge they're busy, restate value, soft close

Why this spacing:
- Day 0-3 gap: enough for Step 1 to be read but not forgotten
- Day 3-4 (1 day gap): rapid follow-up creates urgency cluster
- Day 4-7 (3 day gap): breathing room before channel switch
- Day 7-7 (same day): Steps 4+5 can hit on same day = last push

Key insight: Steps 2 and 4 TIED at 31% each. Step 2 catches competitor-frustrated buyers.
Step 4 catches people who don't read email carefully ("Sent from iPhone" pattern breaks).

DO NOT skip any step — each catches a different buyer archetype.""",
        "market": None,
        "channel": "email",
        "confidence": 0.95,
    },

    # ===== PERSONALIZATION =====
    {
        "pattern_type": "personalization",
        "pattern_key": "city_in_proof_paragraph",
        "title": "{{city}} variable in case study paragraph",
        "description": """Use {{city}} in the proof/case study paragraph, not in the greeting.

Pattern: "Recently helped a {{city}} agency switch from [Competitor] to [our solution],
saving them $X/month..."

Why it works: Creates geographic recognition ("they work with companies in MY city")
without feeling like a mail merge. The city appears in a natural sentence, not as
"Hey, I noticed you're based in {{city}}!" which feels automated.

Evidence: AU-PH campaign with {{city}} personalization (Sydney/Melbourne split)
outperformed generic version. James Martin (Blue Ocean Angels, Sydney) — meeting
booked same day after reading about "a Sydney company."

Custom field setup: Upload contacts with city in custom_fields dict.
SmartLead template: {{city}} resolves from the contact's custom field.

DO NOT: Put {{city}} in subject line or greeting. It belongs in the proof paragraph.""",
        "market": None,
        "channel": "email",
        "confidence": 0.85,
    },

    # ===== CTA =====
    {
        "pattern_type": "cta",
        "pattern_key": "cost_calculation_question",
        "title": "Soft CTA: 'Calculate the cost benefit for your case?'",
        "description": """Step 1 CTA should be a question offering value, not asking for time.

Best: "Would you like to calculate the cost benefit for your case?"
Good: "Can I send you a 2-minute walkthrough video?"
OK: "Open to a quick demo call this week?"

Why it works: The prospect gets something (a calculation, a video) rather than
giving something (their time). "For your case" implies personalization.

Evidence: 9 out of 36 warm leads replied to Step 1. All Step 1 CTAs were
value-offering questions. Zero warm replies came from Steps with "Let me know
if you'd like to schedule a call" type CTAs in isolation.

Step progression:
- Step 1: Value offer ("calculate cost benefit")
- Step 2: Direct ask ("Open to a quick demo call?")
- Step 3: Low-commitment offer ("Can I send you a video?")
- Step 4: Channel switch ("Would it be easier on LinkedIn or Telegram?")
- Step 5: Empathy close ("If improving payments is still a goal, I'm here")

Each CTA matches the step's purpose. Don't use the same CTA pattern twice.""",
        "market": None,
        "channel": "email",
        "confidence": 0.82,
    },

    # ===== TONE =====
    {
        "pattern_type": "tone",
        "pattern_key": "casual_professional_no_hype",
        "title": "Casual-professional tone, zero hype words",
        "description": """Tone that works for B2B cold outreach across all markets:

DO: Write like a person texting a business contact. Short sentences.
Contractions OK. First person. Specific numbers instead of adjectives.

DON'T: Use hype words (revolutionary, cutting-edge, game-changing, innovative,
seamless, robust, leverage). Don't use exclamation marks. Don't say "I hope
this email finds you well."

Evidence: Step 4 uses "Sent from my iPhone" as the signature — the most casual
element — and it triggers 31% of warm replies. The informality breaks the
"automated outreach" pattern and feels like a real person.

Example of good tone:
"We at Easystaff help companies pay freelancers globally with fees under 1%"
(specific number, plain language, no hype)

Example of bad tone:
"Our revolutionary platform seamlessly handles your international payments
with cutting-edge technology" (every word is a red flag)

Russian market note: Same principle applies. Danila's successful EasyStaff RU
sequences use conversational Russian, not corporate-speak.""",
        "market": None,
        "channel": "email",
        "confidence": 0.90,
    },

    # ===== PROOF POINT =====
    {
        "pattern_type": "proof_point",
        "pattern_key": "competitor_displacement_story",
        "title": "Name the competitor they're switching FROM",
        "description": """Step 2 should name specific competitors the prospect likely uses.

Pattern: "Many companies we talk to are moving off Upwork or are frustrated
with Deel's inflexibility."

Why: 90-100% of qualified leads already use SOMETHING. Naming the competitor
creates instant recognition ("that's me!") and positions you as the upgrade.

Competitors to name (by market):
- US/Global: Deel, Rippling, Upwork, Fiverr, Wise, Payoneer
- EU: Deel, Remote.com, Wise, bank wires
- Gulf: Wise, bank transfers, Payoneer
- AU: Deel, Wise, bank transfers

Step 2 should follow with bullet points showing HOW you're better:
- "Cut out the middleman: Save the 10-20% marketplace fees"
- "No annual contracts: Pay only for what you use"
- "Same-day payouts to any country, real human support"

Evidence: Step 2 generates 31% of warm replies — tied with Step 4 for #1.
Avanish Anand (CEO, Zoth) forwarded Step 2 to product lead: "Pls discuss."
CEO delegation = strongest buying signal. Triggered by competitor naming.""",
        "market": None,
        "channel": "email",
        "confidence": 0.91,
    },

    # ===== OPENER =====
    {
        "pattern_type": "opener",
        "pattern_key": "direct_value_statement",
        "title": "Open with what you DO, not who you ARE",
        "description": """First line of Step 1: state the value, not the introduction.

Good: "We at Easystaff help companies pay freelancers globally with fees under 1%"
Bad: "My name is Petr and I'm the BDM at Easystaff, a leading global payroll platform"

Why: The prospect doesn't care who you are. They care what you can do for them.
Lead with the benefit, include the company name naturally.

The word "help" is key — it positions you as solving their problem, not selling.

Evidence: All 9 Step 1 warm replies came from sequences starting with a direct
value statement. Zero came from self-introduction openers.""",
        "market": None,
        "channel": "email",
        "confidence": 0.87,
    },

    # ===== SEQUENCE FLOW =====
    {
        "pattern_type": "sequence_flow",
        "pattern_key": "escalation_from_value_to_empathy",
        "title": "5-step escalation: Value → Competition → Price → Channel → Empathy",
        "description": """Each step serves a different purpose and catches a different buyer type:

Step 1 (VALUE): State what you do, proof point, soft CTA
→ Catches: Impulse buyers with immediate need (25% of warm replies)

Step 2 (COMPETITION): Name competitors, bullet-point advantages
→ Catches: Frustrated users of Deel/Upwork/Wise (31% of warm replies)

Step 3 (PRICE): Transparent pricing, offer to send walkthrough
→ Catches: Enterprise/price-sensitive buyers who need numbers (14%)

Step 4 (CHANNEL SWITCH): "LinkedIn or Telegram?" + "Sent from iPhone"
→ Catches: People who don't read email carefully (31%)

Step 5 (EMPATHY): "I know you're busy", acknowledge they have a solution,
soft restatement of value
→ Catches: Long-cycle buyers who need multiple touches

CRITICAL: Steps 2-5 use EMPTY subject (thread as replies to Step 1).
Only Step 1 has a subject line. This keeps the entire sequence in one
email thread — higher visibility, lower spam risk.

The "Sent from iPhone" in Step 4 is a deliberate pattern-break. It looks
like a real person dashing off a quick message, not an automated sequence.""",
        "market": None,
        "channel": "email",
        "confidence": 0.93,
    },

    # ===== OBJECTION PREEMPT =====
    {
        "pattern_type": "objection_preempt",
        "pattern_key": "pricing_transparency_step3",
        "title": "Show exact pricing in Step 3 (not behind a call)",
        "description": """Step 3 should include transparent pricing numbers.

Pattern: "Our pricing is transparent: from 3% or a flat $39 per task.
Free withdrawals for freelancers. Mass payouts via Excel upload.
For 50+ contractors/month, we offer custom rates below any competitor."

Why: 10% of objections are "too expensive / not worth switching."
Showing pricing proactively filters out non-buyers AND signals confidence.
Hiding pricing behind "let's jump on a call" feels like a trap.

Enterprise trigger: "For 50+ contractors/month, we offer custom rates"
makes enterprise buyers self-identify. Adam Naser (45 roles RFP) replied
to Step 3 specifically because he saw volume pricing was available.

Evidence: Step 3 catches 14% of warm replies — all price-sensitive buyers.
These leads tend to be larger deals (enterprise RFPs, 50+ contractor teams).

Offer to send a "2-minute walkthrough video" as the CTA — low commitment,
high information density.""",
        "market": None,
        "channel": "email",
        "confidence": 0.84,
    },

    # ===== PROOF POINT (NUMBERS) =====
    {
        "pattern_type": "proof_point",
        "pattern_key": "specific_savings_number",
        "title": "Use specific dollar savings, not percentages",
        "description": """Case studies with specific dollar amounts outperform percentage claims.

Good: "saving them $3,000/month on platform fees and exchange rates"
OK: "saving them 70% on international payment costs"
Bad: "significant cost savings on your global payroll"

Why: $3,000/month is tangible and relatable. "70%" requires the prospect to
calculate what 70% of THEIR spend is. "Significant" means nothing.

The number should be realistic for the ICP company size (10-50 employees).
$3,000/month for 50 contractors = $60/contractor/month savings. Believable.

Pair the number with the cost category: "platform fees and exchange rates"
tells them WHAT they're overpaying on, not just that they're overpaying.

Evidence: The "$3,000/month" figure appears in EasyStaff's top-performing
Step 1 across all regional campaigns. Johannes Lotter (50 contractors)
signed after seeing the math applied to his team size.""",
        "market": None,
        "channel": "email",
        "confidence": 0.86,
    },
]


async def main():
    async with async_session_maker() as session:
        # Check if patterns already exist
        from sqlalchemy import select, func
        count = (await session.execute(
            select(func.count()).select_from(CampaignPattern).where(
                CampaignPattern.company_id == COMPANY_ID,
                CampaignPattern.is_active == True,
            )
        )).scalar()

        if count > 0:
            print(f"Already have {count} active patterns. Skipping seed.")
            print("To re-seed, deactivate existing patterns first:")
            print("  UPDATE campaign_patterns SET is_active = false WHERE company_id = 1;")
            return

        for p in PATTERNS:
            pattern = CampaignPattern(
                company_id=COMPANY_ID,
                pattern_type=p["pattern_type"],
                pattern_key=p["pattern_key"],
                title=p["title"],
                description=p["description"],
                market=p.get("market"),
                channel=p.get("channel", "email"),
                confidence=p.get("confidence", 0.8),
                sample_size=170,  # based on 170 EasyStaff campaigns
                evidence_summary="Extracted from EasyStaff Global: 55 warm leads, 3,500+ replies, 170 campaigns",
                version=1,
                is_active=True,
            )
            session.add(pattern)

        await session.commit()
        print(f"Seeded {len(PATTERNS)} campaign patterns")

        # Print summary
        for p in PATTERNS:
            print(f"  [{p['pattern_type']}] {p['title']} (confidence: {p['confidence']})")


if __name__ == "__main__":
    asyncio.run(main())
