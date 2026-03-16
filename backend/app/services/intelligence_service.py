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


def classify_reply(reply_text: str, category: str, campaign_name: str, channel: str) -> dict:
    """
    Classify a single reply. Returns dict with intent, warmth, offer, segment, etc.
    Deterministic rules — no AI needed for 80%+ of cases.
    """
    text = (reply_text or "").strip()
    text_lower = text.lower()

    # ── Empty replies ──
    if not text or len(text) < 3:
        return {
            "intent": "empty",
            "warmth_score": 0,
            "offer_responded_to": "general",
            "campaign_segment": detect_segment(campaign_name),
            "sequence_type": detect_sequence_type(campaign_name, channel),
            "language": "unknown",
        }

    # ── Bounce / delivery failure ──
    bounce_patterns = ["не удалось выполнить доставку", "delivery failed", "undeliverable", "message expired", "не удалось найти"]
    if any(p in text_lower for p in bounce_patterns):
        return _result("bounce", 0, "general", campaign_name, channel, text)

    # ── Auto-response ──
    auto_patterns = ["i have received your email", "will get back to you", "your ticket", "has been received",
                     "mixmax to route", "auto-reply", "автоответ", "out of the office", "returning on"]
    if any(p in text_lower for p in auto_patterns):
        return _result("auto_response", 0, "general", campaign_name, channel, text)

    # ── Gibberish ──
    if len(text) < 5 and not any(c.isalpha() for c in text):
        return _result("gibberish", 0, "general", campaign_name, channel, text)

    # ── Schedule call (warmth 5) ──
    schedule_patterns = ["созвонимся", "давайте встретиться", "schedule a call", "let's meet", "calendly",
                         "let me know your availability", "book a time", "here is my calendar",
                         "can we speak", "давайте обсудим", "готовы встретиться",
                         "let's have a call", "happy to have a chat", "let's schedule",
                         "предлагаю понедельник", "предлагаю вторник", "какие у вас слоты"]
    if any(p in text_lower for p in schedule_patterns) or "calendly.com" in text_lower:
        return _result("schedule_call", 5, detect_offer(text, campaign_name), campaign_name, channel, text)

    # ── Send info (warmth 4) ──
    send_info_patterns = ["пришлите", "присылайте", "send one pager", "send me details", "share details",
                          "send over", "please share", "отправляйте", "направьте", "высылай",
                          "send me more", "share the one pager", "send us the rates", "please go ahead",
                          "давай посмотрим", "пришлите предложение", "send your",
                          "prislite", "could you send", "can you share", "готов рассмотреть"]
    if any(p in text_lower for p in send_info_patterns):
        return _result("send_info", 4, detect_offer(text, campaign_name), campaign_name, channel, text)

    # ── Interested vague (warmth 4) ──
    interested_patterns = ["да интересно", "да, интересно", "sounds interesting", "interested",
                           "интересное предложение", "happy to explore", "explore potential",
                           "this is relevant", "that sounds", "would be interested"]
    if any(p in text_lower for p in interested_patterns) and category in ("interested", "meeting_request"):
        return _result("interested_vague", 4, detect_offer(text, campaign_name), campaign_name, channel, text)

    # ── Redirect to colleague (warmth 3) ──
    redirect_patterns = ["talk to my colleague", "forwarded your email", "redirected to",
                         "contact my colleague", "переслал коллеге", "направьте нашему",
                         "направила коллегам", "got your contact from"]
    if any(p in text_lower for p in redirect_patterns):
        return _result("redirect_colleague", 3, detect_offer(text, campaign_name), campaign_name, channel, text)

    # ── Pricing question (warmth 3) ──
    pricing_patterns = ["rates", "pricing", "fees", "комиссия", "тарифы", "условия", "процент за",
                        "how much", "сколько стоит", "стоимость"]
    if any(p in text_lower for p in pricing_patterns) and category in ("question", "interested", "meeting_request"):
        return _result("pricing", 3, detect_offer(text, campaign_name), campaign_name, channel, text)

    # ── Compliance / legal question (warmth 3) ──
    compliance_patterns = ["комплаенс", "compliance", "лицензи", "license", "regulatory",
                           "гарантии сохранности", "сегрегированн", "ндс", "vat"]
    if any(p in text_lower for p in compliance_patterns):
        return _result("compliance", 3, detect_offer(text, campaign_name), campaign_name, channel, text)

    # ── How it works question (warmth 3) ──
    how_patterns = ["how does it work", "как это работает", "как происходит", "step-by-step",
                    "can you explain", "расскажите подробнее", "как подключить"]
    if any(p in text_lower for p in how_patterns):
        return _result("how_it_works", 3, detect_offer(text, campaign_name), campaign_name, channel, text)

    # ── Adjacent demand (warmth 3) — wants reverse or adjacent service ──
    adjacent_patterns = ["обратная задача", "он рамп", "on-ramp", "fiat to crypto",
                         "покупать крипту", "карты мир", "в обратном порядке", "кастоди"]
    if any(p in text_lower for p in adjacent_patterns):
        return _result("adjacent_demand", 3, detect_offer(text, campaign_name), campaign_name, channel, text)

    # ── Specific use case question (warmth 3) ──
    if category == "question" and len(text) > 50:
        return _result("specific_use_case", 3, detect_offer(text, campaign_name), campaign_name, channel, text)

    # ── Spam complaint (warmth 1) ──
    spam_patterns = ["mass mailing", "how did you get my", "удалите мой", "remove from list",
                     "перестаньте писать", "stop writing", "stop emailing", "откуда у вас мой"]
    if any(p in text_lower for p in spam_patterns):
        return _result("spam_complaint", 1, "general", campaign_name, channel, text)

    # ── Hard no (warmth 1) ──
    hard_no_patterns = ["нет", "no thanks", "not interested", "не заинтересован", "не нужно"]
    if category == "not_interested" and len(text) < 30:
        return _result("hard_no", 1, "general", campaign_name, channel, text)

    # ── No crypto (warmth 1) ──
    no_crypto_patterns = ["не работаем с крипт", "don't deal in crypto", "don't use crypto",
                          "крипты нет", "not crypto", "no crypto", "не используем крипт"]
    if any(p in text_lower for p in no_crypto_patterns):
        return _result("no_crypto", 1, "general", campaign_name, channel, text)

    # ── Regulatory objection (warmth 1) ──
    regulatory_patterns = ["регулятор", "regulator", "supervisor", "compliance issue",
                           "только через локальные", "невозможности реализации", "legal"]
    if any(p in text_lower for p in regulatory_patterns) and category == "not_interested":
        return _result("regulatory", 1, "general", campaign_name, channel, text)

    # ── Not now / maybe later (warmth 2) ──
    not_now_patterns = ["пока не актуальн", "not now", "maybe later", "в будущем", "пока нет",
                        "not a priority", "не приоритет", "сохранил контакт", "stay in touch",
                        "оставаться на связи", "буду иметь ввиду", "if that changes",
                        "currently not", "at this time", "на данный момент не"]
    if any(p in text_lower for p in not_now_patterns):
        return _result("not_now", 2, "general", campaign_name, channel, text)

    # ── Have solution (warmth 2) ──
    have_solution_patterns = ["у нас свой", "we have our own", "already have", "уже пользуемся",
                              "своя инфраструктур", "own infrastructure", "own crypto"]
    if any(p in text_lower for p in have_solution_patterns):
        return _result("have_solution", 2, detect_offer(text, campaign_name), campaign_name, channel, text)

    # ── Not relevant (warmth 1) ──
    if category == "not_interested":
        return _result("not_relevant", 1, "general", campaign_name, channel, text)

    # ── Wrong person forward (warmth 0) ──
    if category == "wrong_person":
        return _result("wrong_person_forward", 0, "general", campaign_name, channel, text)

    # ── Unsubscribe ──
    if category == "unsubscribe":
        return _result("hard_no", 1, "general", campaign_name, channel, text)

    # ── Acknowledgment only ──
    ack_patterns = ["thanks for connecting", "nice to connect", "спасибо", "thanks", "thank you"]
    if len(text) < 40 and any(p in text_lower for p in ack_patterns):
        return _result("auto_response", 0, "general", campaign_name, channel, text)

    # ── Fallback: use existing category ──
    if category in ("interested", "meeting_request"):
        return _result("interested_vague", 4, detect_offer(text, campaign_name), campaign_name, channel, text)
    if category == "question":
        return _result("specific_use_case", 3, detect_offer(text, campaign_name), campaign_name, channel, text)

    return _result("auto_response", 0, "general", campaign_name, channel, text)


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
