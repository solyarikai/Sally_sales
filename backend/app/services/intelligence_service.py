"""
Reply Intelligence Service — classify replies by offer, intent, warmth, segment.

Deterministic rules first, AI fallback for ambiguous cases.
"""
import logging
import re
from typing import Optional

from sqlalchemy import select, func, and_, case, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reply import ProcessedReply, ThreadMessage
from app.models.reply_analysis import ReplyAnalysis
from app.models.contact import Project

logger = logging.getLogger(__name__)

# ── Campaign segment patterns ──────────────────────────────────

SEGMENT_PATTERNS = {
    "russian_dms": ["Russian DM", "RUS DM", "Rus DM", "Rus Data", "ES - Rus", "INXY - Rus"],
    "conference": ["ICE", "Token2049", "Token 2049", "Money20", "IGB", "Ecom Berlin", "Luma", "SEP", "London Tech"],
    "payments": ["Crypto Payments", "PSP", "FinTech", "Merchants", "Companies using", "Companies Acc", "Cryptwerk"],
    "trading": ["Trading", "Investment", "Tokenization"],
    "creator": ["Creator", "Creators", "Monetization"],
    "gaming": ["Gaming", "GameFi", "GameZ", "iGaming", "E-Sport", "P2E", "Crypto games"],
    "saas": ["SaaS", "Cloud", "eSIM", "EdTech", "Hosting", "Mobile", "CpaaS"],
    "ecommerce": ["Shopify", "Digital Marketplace", "Ecom"],
    "cross_sell": ["ES ", "ES-", "Baxity", "INXY-ES", "feature-", "lookalike"],
}


def detect_segment(campaign_name: str) -> str:
    """Map campaign name to target segment."""
    for segment, patterns in SEGMENT_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in campaign_name.lower():
                return segment
    return "other"


def detect_sequence_type(campaign_name: str, channel: str) -> str:
    """Determine the type of outreach sequence."""
    name_lower = campaign_name.lower()
    if any(kw in name_lower for kw in ["ice", "token2049", "token 2049", "money20", "igb", "ecom berlin", "luma", "sep", "london"]):
        return "conference_followup"
    if "personalization" in name_lower or "personalized" in name_lower:
        return "personalized"
    if channel == "linkedin":
        return "cold_linkedin"
    return "cold_email"


def detect_offer(reply_text: str, campaign_name: str) -> str:
    """Determine which INXY product the reply responds to."""
    text = (reply_text or "").lower()

    # Keywords in reply text
    payout_kw = ["выплат", "payout", "подрядчик", "contractor", "mass payment", "disbursement", "payroll"]
    otc_kw = ["otc", "обмен", "exchange", "treasury", "ликвидност", "конвертаци"]
    paygate_kw = ["прием платеж", "accept payment", "paygate", "payment gateway", "платежный", "принимать платеж"]

    if any(kw in text for kw in payout_kw):
        return "payout"
    if any(kw in text for kw in otc_kw):
        return "otc"
    if any(kw in text for kw in paygate_kw):
        return "paygate"

    # Campaign-specific defaults
    name_lower = campaign_name.lower()
    if any(kw in name_lower for kw in ["monetization", "creator", "eor", "f&p"]):
        return "payout"
    if any(kw in name_lower for kw in ["luma", "trading"]):
        return "otc"

    return "general"


def detect_language(text: str) -> str:
    """Simple language detection based on character ranges."""
    if not text:
        return "unknown"
    cyrillic = len(re.findall(r'[\u0400-\u04FF]', text))
    latin = len(re.findall(r'[a-zA-Z]', text))
    if cyrillic > latin:
        return "ru"
    return "en"


def _strip_quoted_and_signature(text: str) -> str:
    """
    Extract only the lead's own words — strip quoted outbound messages,
    email signatures, and forwarded content. This prevents false positives
    from keywords in INXY's outbound (e.g. "лицензии VASP") or
    signatures with Calendly links.
    """
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        # Stop at quoted text markers
        if stripped.startswith(">") or stripped.startswith("&gt;"):
            break
        # Stop at common quote headers
        if any(marker in stripped.lower() for marker in [
            "from: serge", "от: serge", "from: hugo", "from: tamara", "from: ruslan",
            "wrote:", "написал:", "пишет:", "sent:", "envoyé :",
            "on ", "am ", "le ", "el ",  # date prefixes before quoted text
        ]):
            # Only break if this looks like a quote header (contains date-like patterns)
            if any(c.isdigit() for c in stripped) or "wrote" in stripped.lower() or "написал" in stripped.lower():
                break
        # Stop at signature blocks
        if stripped == "--" or stripped == "---" or stripped.startswith("-- "):
            break
        # Stop at image/cid references (signature images)
        if "[cid:" in stripped:
            break
        clean_lines.append(line)

    result = "\n".join(clean_lines).strip()
    # Also strip HTML tags
    result = re.sub(r'<[^>]+>', ' ', result)
    result = re.sub(r'&\w+;', ' ', result)  # &nbsp; etc
    result = re.sub(r'\s+', ' ', result).strip()
    return result


def classify_reply(reply_text: str, category: str, campaign_name: str, channel: str) -> dict:
    """
    Classify a single reply. Architecture:
    1. Category gates — trust the AI classifier's category for hard decisions
    2. Clean text — strip quoted outbound and signatures
    3. Keyword matching — only on the lead's own words
    """
    raw_text = (reply_text or "").strip()

    # ── Empty replies ──
    if not raw_text or len(raw_text) < 3:
        return {
            "intent": "empty",
            "warmth_score": 0,
            "offer_responded_to": "general",
            "campaign_segment": detect_segment(campaign_name),
            "sequence_type": detect_sequence_type(campaign_name, channel),
            "language": "unknown",
        }

    # Detect follow-up drafts (system-generated, not real replies)
    if "(Follow-up" in raw_text or "(follow-up" in raw_text:
        return _result("empty", 0, "general", campaign_name, channel, raw_text)

    # Clean text = lead's own words only (no quoted outbound, no signatures)
    text = _strip_quoted_and_signature(raw_text)
    text_lower = text.lower()
    raw_lower = raw_text.lower()

    # ═══════════════════════════════════════════════════════════════
    # PHASE 1: CATEGORY GATES — trust the AI classifier first
    # The original category (interested/not_interested/etc) is from
    # the reply processing AI. It's right ~90% of the time.
    # Never promote a not_interested/unsubscribe/wrong_person to warm.
    # ═══════════════════════════════════════════════════════════════

    is_cold_category = category in ("not_interested", "unsubscribe", "wrong_person")
    is_warm_category = category in ("interested", "meeting_request")
    is_question_category = category == "question"

    # ── Bounce / delivery failure (any category) ──
    bounce_patterns = ["не удалось выполнить доставку", "delivery failed", "undeliverable",
                       "message expired", "не удалось найти", "fehler bei der nachrichtenzustellung",
                       "non-delivery", "returned to sender", "mailbox not found"]
    if any(p in raw_lower for p in bounce_patterns):
        return _result("bounce", 0, "general", campaign_name, channel, raw_text)

    # ── Auto-response (any category) ──
    auto_patterns = ["i have received your email", "will get back to you", "your ticket",
                     "has been received", "mixmax to route", "auto-reply", "автоответ",
                     "out of the office", "returning on", "support representative will",
                     "již v naší společnosti nepůsobí", "je ne suis pas disponible"]
    if any(p in raw_lower for p in auto_patterns):
        return _result("auto_response", 0, "general", campaign_name, channel, raw_text)

    # ── Gibberish ──
    if len(text) < 5 and not any(c.isalpha() for c in text):
        return _result("gibberish", 0, "general", campaign_name, channel, raw_text)

    # ═══════════════════════════════════════════════════════════════
    # PHASE 2: COLD CATEGORIES — never promote to warm
    # If the AI said not_interested/unsubscribe/wrong_person, classify
    # the specific type of rejection but NEVER warmth > 2
    # ═══════════════════════════════════════════════════════════════

    if category == "wrong_person":
        return _result("wrong_person_forward", 0, "general", campaign_name, channel, raw_text)

    if category == "unsubscribe":
        # Check if it's actually a spam complaint
        spam_patterns = ["mass mailing", "how did you get my", "stop writing", "stop emailing",
                         "перестаньте писать", "откуда у вас мой", "why do you keep"]
        if any(p in text_lower for p in spam_patterns):
            return _result("spam_complaint", 1, "general", campaign_name, channel, raw_text)
        return _result("hard_no", 1, "general", campaign_name, channel, raw_text)

    if category == "not_interested":
        # Subclassify the type of rejection
        spam_patterns = ["mass mailing", "how did you get my", "stop writing", "stop emailing",
                         "перестаньте писать", "откуда у вас мой", "why do you keep",
                         "please stop", "пожалуйста, перестань"]
        if any(p in text_lower for p in spam_patterns):
            return _result("spam_complaint", 1, "general", campaign_name, channel, raw_text)

        no_crypto_patterns = ["не работаем с крипт", "don't deal in crypto", "don't use crypto",
                              "крипты нет", "not crypto", "no crypto", "не используем крипт",
                              "we do not use crypto", "не связываемся с крипто"]
        if any(p in text_lower for p in no_crypto_patterns):
            return _result("no_crypto", 1, "general", campaign_name, channel, raw_text)

        regulatory_patterns = ["регулятор", "regulator", "supervisor not crypto",
                               "только через локальные", "невозможности реализации",
                               "лицензирование останавливает", "requires crypto license"]
        if any(p in text_lower for p in regulatory_patterns):
            return _result("regulatory", 1, "general", campaign_name, channel, raw_text)

        not_now_patterns = ["пока не актуальн", "not now", "maybe later", "в будущем", "пока нет",
                            "not a priority", "не приоритет", "сохранил контакт", "stay in touch",
                            "оставаться на связи", "буду иметь ввиду", "if that changes",
                            "currently not", "at this time", "на данный момент не",
                            "not at this stage", "not looking", "not in need"]
        if any(p in text_lower for p in not_now_patterns):
            return _result("not_now", 2, "general", campaign_name, channel, raw_text)

        have_solution_patterns = ["у нас свой", "we have our own", "already have", "уже пользуемся",
                                  "fully covered", "own infrastructure", "own crypto"]
        if any(p in text_lower for p in have_solution_patterns):
            return _result("have_solution", 2, "general", campaign_name, channel, raw_text)

        # Short rejections
        if len(text) < 50:
            return _result("hard_no", 1, "general", campaign_name, channel, raw_text)

        return _result("not_relevant", 1, "general", campaign_name, channel, raw_text)

    # ═══════════════════════════════════════════════════════════════
    # PHASE 3: WARM + QUESTION CATEGORIES — subclassify with keywords
    # Now we only have interested/meeting_request/question/other.
    # Safe to check for warm signals on CLEANED text.
    # ═══════════════════════════════════════════════════════════════

    if is_warm_category or is_question_category:
        # ── GUARD: empty or very short reply text ──
        if not text or len(text) < 5:
            return _result("empty", 0, "general", campaign_name, channel, raw_text)

        # ── GUARD: very short text — only trust if it has clear warm signal ──
        if len(text) < 20:
            short_lower = text.lower()
            # These short patterns are genuinely warm
            short_warm = ["sure", "ok", "да", "хорошо", "ок", "yes", "давайте",
                          "monday", "tuesday", "wednesday", "thursday", "friday",
                          "понедельник", "вторник", "cal link", "calendly"]
            if any(p in short_lower for p in short_warm):
                if is_warm_category:
                    return _result("interested_vague", 4, "general", campaign_name, channel, raw_text)
            # Short acknowledgments = noise
            short_ack = ["thanks", "thank you", "спасибо", "cheers", "thx"]
            if any(p in short_lower for p in short_ack):
                return _result("auto_response", 0, "general", campaign_name, channel, raw_text)

        # ── GUARD: contradictory signals — lead says negative but AI said warm ──
        negative_signals = ["not interested", "not relevant", "не интересует", "не актуальн",
                            "отпишите", "отписать", "unsubscribe", "remove me",
                            "we are not", "I am not", "no thanks", "не нужно",
                            "don't respond to mass", "spam"]
        if any(p in text_lower for p in negative_signals):
            # AI was wrong — this is actually a rejection
            return _result("not_relevant", 1, "general", campaign_name, channel, raw_text)

        # ── Schedule call (warmth 5) — on CLEANED text only ──
        schedule_patterns = ["созвонимся", "давайте встретиться", "schedule a call", "let's meet",
                             "let me know your availability", "book a time",
                             "can we speak", "давайте обсудим", "готовы встретиться",
                             "let's have a call", "happy to have a chat", "let's schedule",
                             "забукайте", "hop on a call", "arrange a call",
                             "готовы с вами встретиться"]
        # Calendly link in cleaned text (not in signature of quoted outbound)
        has_calendly = "calendly.com" in text_lower
        has_schedule = any(p in text_lower for p in schedule_patterns)
        # Time slot offers
        has_time_slot = bool(re.search(r'\b\d{1,2}[:.]\d{2}\b', text)) and any(
            w in text_lower for w in ["monday", "tuesday", "wednesday", "thursday", "friday",
                                       "понедельник", "вторник", "среда", "четверг", "пятница",
                                       "пн", "вт", "ср", "чт", "пт", "am", "pm", "cet"])
        if has_schedule or has_calendly or has_time_slot:
            return _result("schedule_call", 5, detect_offer(text, campaign_name), campaign_name, channel, raw_text)

        # ── Send info (warmth 4) ──
        send_info_patterns = ["пришлите", "присылайте", "send one pager", "send me details",
                              "share details", "send over", "please share", "отправляйте",
                              "направьте", "высылай", "send me more", "share the one pager",
                              "send us the rates", "please go ahead", "давай посмотрим",
                              "send your", "could you send", "can you share",
                              "готов рассмотреть", "посмотрю", "ознакомлюсь", "изучим"]
        if any(p in text_lower for p in send_info_patterns):
            return _result("send_info", 4, detect_offer(text, campaign_name), campaign_name, channel, raw_text)

        # ── Pricing question (warmth 3) ──
        pricing_patterns = ["rates", "pricing", "fees", "комиссия", "тарифы", "процент за",
                            "how much", "сколько стоит", "стоимость", "какие условия",
                            "send us the rates"]
        if any(p in text_lower for p in pricing_patterns):
            return _result("pricing", 3, detect_offer(text, campaign_name), campaign_name, channel, raw_text)

        # ── Compliance / legal question (warmth 3) — ONLY if they're asking ──
        compliance_q_patterns = ["комплаенс", "гарантии сохранности", "сегрегированн",
                                 "ндс", "vat", "ваш комплаенс", "your compliance",
                                 "какие лицензии", "which licenses", "are you regulated"]
        if any(p in text_lower for p in compliance_q_patterns) and is_question_category:
            return _result("compliance", 3, detect_offer(text, campaign_name), campaign_name, channel, raw_text)

        # ── How it works question (warmth 3) ──
        how_patterns = ["how does it work", "как это работает", "как происходит",
                        "can you explain", "расскажите подробнее", "как подключить",
                        "поподробнее", "more details", "further details"]
        if any(p in text_lower for p in how_patterns):
            return _result("how_it_works", 3, detect_offer(text, campaign_name), campaign_name, channel, raw_text)

        # ── Adjacent demand (warmth 3) ──
        adjacent_patterns = ["обратная задача", "он рамп", "on-ramp", "fiat to crypto",
                             "покупать крипту", "карты мир", "в обратном порядке", "кастоди"]
        if any(p in text_lower for p in adjacent_patterns):
            return _result("adjacent_demand", 3, detect_offer(text, campaign_name), campaign_name, channel, raw_text)

        # ── Interested vague (warmth 4) ──
        interested_patterns = ["да интересно", "да, интересно", "sounds interesting",
                               "интересное предложение", "happy to explore", "explore potential",
                               "this is relevant", "would be interested", "да, давай",
                               "да, пришлите", "yes please", "sure"]
        if any(p in text_lower for p in interested_patterns) and is_warm_category:
            return _result("interested_vague", 4, detect_offer(text, campaign_name), campaign_name, channel, raw_text)

        # ── Redirect to colleague (warmth 3) ──
        redirect_patterns = ["talk to my colleague", "forwarded your email", "redirected to",
                             "contact my colleague", "переслал коллеге", "направьте нашему",
                             "направила коллегам", "got your contact from"]
        if any(p in text_lower for p in redirect_patterns):
            return _result("redirect_colleague", 3, detect_offer(text, campaign_name), campaign_name, channel, raw_text)

        # ── Specific use case (warmth 3) — question with substance ──
        if is_question_category and len(text) > 50:
            return _result("specific_use_case", 3, detect_offer(text, campaign_name), campaign_name, channel, raw_text)

        # ── Fallback for warm categories ──
        if is_warm_category:
            return _result("interested_vague", 4, detect_offer(text, campaign_name), campaign_name, channel, raw_text)
        if is_question_category:
            return _result("specific_use_case", 3, detect_offer(text, campaign_name), campaign_name, channel, raw_text)

    # ═══════════════════════════════════════════════════════════════
    # PHASE 4: "OTHER" CATEGORY — could be anything
    # These need more careful analysis since AI wasn't sure.
    # ═══════════════════════════════════════════════════════════════

    # ── GUARD: check for negative signals first in "other" ──
    negative_in_other = ["not interested", "не интересует", "не актуальн", "unsubscribe",
                         "отпишите", "remove me", "spam", "no thanks", "не нужно",
                         "we are not", "I am not"]
    if any(p in text_lower for p in negative_in_other):
        return _result("not_relevant", 1, "general", campaign_name, channel, raw_text)

    # Acknowledgment only (very short, no substance)
    if len(text) < 40:
        ack_patterns = ["thanks for connecting", "nice to connect", "thanks", "thank you",
                        "спасибо", "cheers", "regards"]
        if any(p in text_lower for p in ack_patterns):
            return _result("auto_response", 0, "general", campaign_name, channel, raw_text)
        # Very short other = gibberish/noise
        if len(text) < 15:
            return _result("gibberish", 0, "general", campaign_name, channel, raw_text)

    # Check if it has STRONG warm signals even though category is "other"
    # Be strict here — only unmistakable signals, not broad words
    strong_warm = ["созвонимся", "давайте обсудим", "schedule a call", "let's meet",
                   "давайте встретиться", "пришлите предложение", "send one pager",
                   "calendly.com", "happy to explore", "interested in your"]
    if any(p in text_lower for p in strong_warm) and len(text) > 20:
        return _result("interested_vague", 3, detect_offer(text, campaign_name), campaign_name, channel, raw_text)

    return _result("auto_response", 0, "general", campaign_name, channel, raw_text)


def _result(intent: str, warmth: int, offer: str, campaign_name: str, channel: str, text: str) -> dict:
    return {
        "intent": intent,
        "warmth_score": warmth,
        "offer_responded_to": offer,
        "campaign_segment": detect_segment(campaign_name),
        "sequence_type": detect_sequence_type(campaign_name, channel),
        "language": detect_language(text),
    }


# ── Intent group mapping ──

INTENT_GROUPS = {
    "warm": ["send_info", "schedule_call", "interested_vague", "redirect_colleague"],
    "questions": ["pricing", "how_it_works", "compliance", "specific_use_case", "adjacent_demand"],
    "soft_objection": ["not_now", "have_solution"],
    "hard_objection": ["not_relevant", "no_crypto", "regulatory", "hard_no", "spam_complaint"],
    "noise": ["empty", "auto_response", "bounce", "gibberish", "wrong_person_forward"],
}

def get_intent_group(intent: str) -> str:
    for group, intents in INTENT_GROUPS.items():
        if intent in intents:
            return group
    return "noise"


# ── Batch analysis ──

async def analyze_project_replies(session: AsyncSession, project_id: int) -> dict:
    """
    Classify all unanalyzed replies for a project. Returns stats.
    """
    # Get project's campaign filters
    project = await session.get(Project, project_id)
    if not project:
        return {"error": "Project not found"}

    campaign_filters = project.campaign_filters or []
    if not campaign_filters:
        return {"error": "No campaign_filters configured for project"}

    # Get all non-OOO replies for this project that don't have analysis yet
    already_analyzed = select(ReplyAnalysis.processed_reply_id)

    query = (
        select(ProcessedReply)
        .where(
            and_(
                ProcessedReply.campaign_name.in_(campaign_filters),
                ProcessedReply.category != "out_of_office",
                ~ProcessedReply.id.in_(already_analyzed),
            )
        )
        .order_by(ProcessedReply.received_at.desc())
    )

    result = await session.execute(query)
    replies = result.scalars().all()

    classified = 0
    for reply in replies:
        reply_text = reply.reply_text or reply.email_body or ""
        classification = classify_reply(
            reply_text=reply_text,
            category=reply.category or "other",
            campaign_name=reply.campaign_name or "",
            channel=reply.channel or "email",
        )

        analysis = ReplyAnalysis(
            processed_reply_id=reply.id,
            project_id=project_id,
            offer_responded_to=classification["offer_responded_to"],
            intent=classification["intent"],
            warmth_score=classification["warmth_score"],
            campaign_segment=classification["campaign_segment"],
            sequence_type=classification["sequence_type"],
            language=classification["language"],
            reasoning="deterministic_v1",
            analyzer_model="rules_v1",
        )
        session.add(analysis)
        classified += 1

    await session.flush()
    return {"classified": classified, "project_id": project_id}


async def get_intelligence_summary(session: AsyncSession, project_id: int) -> dict:
    """Get summary stats for the intelligence dashboard."""
    query = (
        select(
            ReplyAnalysis.intent,
            ReplyAnalysis.offer_responded_to,
            ReplyAnalysis.warmth_score,
            ReplyAnalysis.campaign_segment,
            func.count().label("cnt"),
        )
        .where(ReplyAnalysis.project_id == project_id)
        .group_by(
            ReplyAnalysis.intent,
            ReplyAnalysis.offer_responded_to,
            ReplyAnalysis.warmth_score,
            ReplyAnalysis.campaign_segment,
        )
    )
    result = await session.execute(query)
    rows = result.all()

    # Aggregate
    by_group = {"warm": 0, "questions": 0, "soft_objection": 0, "hard_objection": 0, "noise": 0}
    by_offer = {}
    by_segment = {}
    by_intent = {}
    total = 0

    for intent, offer, warmth, segment, cnt in rows:
        total += cnt
        group = get_intent_group(intent or "empty")
        by_group[group] = by_group.get(group, 0) + cnt
        by_offer[offer or "general"] = by_offer.get(offer or "general", 0) + cnt
        by_segment[segment or "other"] = by_segment.get(segment or "other", 0) + cnt
        by_intent[intent or "empty"] = by_intent.get(intent or "empty", 0) + cnt

    return {
        "total": total,
        "by_group": by_group,
        "by_offer": dict(sorted(by_offer.items(), key=lambda x: -x[1])),
        "by_segment": dict(sorted(by_segment.items(), key=lambda x: -x[1])),
        "by_intent": dict(sorted(by_intent.items(), key=lambda x: -x[1])),
    }
