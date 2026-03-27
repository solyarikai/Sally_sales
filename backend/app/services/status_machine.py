"""
13-Status Lead Funnel State Machine.

Statuses (in funnel order):
  TO_BE_SENT → SENT → [AI classifies reply] →
    INTERESTED → NEGOTIATING_MEETING → SCHEDULED →
      MEETING_HELD → QUALIFIED | NOT_QUALIFIED
      MEETING_NO_SHOW → SCHEDULED (reschedule) | NOT_INTERESTED
      MEETING_RESCHEDULED → SCHEDULED (new date)
    NOT_INTERESTED — reachable from ANY status, re-engageable
    OOO → INTERESTED (after follow-up)
    UNSUBSCRIBED (terminal, global blacklist)

Rules:
  - Forward-only for positive stages: can't go backwards in the funnel
  - Negative statuses (not_interested, ooo) reachable from ANY status
  - NOT_INTERESTED is NOT terminal — lead can re-engage (→ interested, negotiating_meeting)
  - Terminal statuses: NOT_QUALIFIED, UNSUBSCRIBED — no transitions out
  - AI classification maps reply categories to the first post-reply status
"""
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# ── All valid statuses ──

STATUSES = [
    "to_be_sent",
    "sent",
    "interested",
    "not_interested",
    "ooo",
    "unsubscribed",
    "negotiating_meeting",
    "scheduled",
    "meeting_held",
    "meeting_no_show",
    "meeting_rescheduled",
    "qualified",
    "not_qualified",
]

# Terminal statuses — no transitions out
# not_interested is intentionally NOT terminal: leads can re-engage
TERMINAL = {"not_qualified", "unsubscribed"}

# Funnel rank for forward-only enforcement
STATUS_RANK = {
    "to_be_sent": 0,
    "sent": 1,
    "interested": 2,
    "not_interested": 2,
    "ooo": 2,
    "unsubscribed": 2,
    "negotiating_meeting": 3,
    "scheduled": 4,
    "meeting_held": 5,
    "meeting_no_show": 5,
    "meeting_rescheduled": 5,
    "qualified": 6,
    "not_qualified": 6,
}

# ── Valid transitions (from → set of allowed targets) ──

VALID_TRANSITIONS = {
    "to_be_sent": {"sent"},
    "sent": {
        "interested", "not_interested", "ooo", "unsubscribed",
        "negotiating_meeting",  # direct if reply is meeting request
    },
    "interested": {"negotiating_meeting", "not_interested", "unsubscribed"},
    "ooo": {"interested", "not_interested", "unsubscribed", "negotiating_meeting"},
    "negotiating_meeting": {"scheduled", "not_interested", "unsubscribed"},
    "scheduled": {
        "meeting_held", "meeting_no_show", "meeting_rescheduled",
        "not_interested", "unsubscribed",
    },
    "meeting_held": {"qualified", "not_qualified", "not_interested", "unsubscribed"},
    "meeting_no_show": {"scheduled", "not_interested", "unsubscribed"},
    "meeting_rescheduled": {"scheduled", "not_interested", "unsubscribed"},
    # not_interested is NOT terminal — lead can re-engage
    "not_interested": {"interested", "negotiating_meeting", "unsubscribed"},
    # Terminal — no transitions out
    "not_qualified": set(),
    "unsubscribed": set(),
    "qualified": set(),
}

# ── AI classification → CRM status mapping ──

AI_CATEGORY_TO_STATUS = {
    "interested": "interested",
    "meeting_request": "negotiating_meeting",
    "not_interested": "not_interested",
    "out_of_office": "ooo",
    "unsubscribe": "unsubscribed",
    "question": "interested",
    "wrong_person": "not_interested",
    "other": "interested",  # default optimistic
}

# ── Legacy status migration (old statuses → new) ──

LEGACY_STATUS_MAP = {
    "lead": "to_be_sent",
    "new": "to_be_sent",
    "contacted": "sent",
    "replied": "interested",
    "warm": "interested",
    "scheduling": "negotiating_meeting",
    "out_of_office": "ooo",
    "wrong_person": "not_interested",
    "touched": "sent",
}


def normalize_status(status: Optional[str]) -> str:
    """Map legacy/unknown status to the 13-status system."""
    if not status:
        return "to_be_sent"
    s = status.strip().lower()
    if s in STATUS_RANK:
        return s
    return LEGACY_STATUS_MAP.get(s, "to_be_sent")


def can_transition(current: str, target: str) -> bool:
    """Check if transition from current to target is allowed."""
    current = normalize_status(current)
    target = normalize_status(target)
    if current == target:
        return True  # no-op is always allowed
    return target in VALID_TRANSITIONS.get(current, set())


def transition_status(
    current: str,
    target: str,
    force: bool = False,
) -> Tuple[str, bool, str]:
    """
    Attempt a status transition.

    Args:
        current: Current status (may be legacy)
        target: Desired new status
        force: Skip validation (for admin overrides)

    Returns:
        (new_status, success, message)
    """
    current_norm = normalize_status(current)
    target_norm = normalize_status(target)

    if current_norm == target_norm:
        return current_norm, True, "no change"

    if force:
        logger.info(f"Status FORCE transition: {current_norm} → {target_norm}")
        return target_norm, True, "forced"

    if can_transition(current_norm, target_norm):
        logger.info(f"Status transition: {current_norm} → {target_norm}")
        return target_norm, True, "ok"

    msg = f"Invalid transition: {current_norm} → {target_norm}"
    logger.warning(msg)
    return current_norm, False, msg


def status_from_ai_category(category: str) -> str:
    """Map an AI classification category to a CRM status."""
    return AI_CATEGORY_TO_STATUS.get(category, "interested")


def get_status_rank(status: str) -> int:
    """Get the funnel rank of a status (higher = further in funnel)."""
    return STATUS_RANK.get(normalize_status(status), 0)


def is_terminal(status: str) -> bool:
    """Check if a status is terminal (no further transitions)."""
    return normalize_status(status) in TERMINAL


def is_warm(status: str) -> bool:
    """Check if a status indicates a warm/active lead."""
    s = normalize_status(status)
    return s in {
        "interested", "negotiating_meeting", "scheduled",
        "meeting_held", "meeting_rescheduled",
    }


def is_meeting_stage(status: str) -> bool:
    """Check if a status is in the meetings zone."""
    return normalize_status(status) in {
        "negotiating_meeting", "scheduled", "meeting_held",
        "meeting_no_show", "meeting_rescheduled",
    }


def needs_qualification(status: str) -> bool:
    """Check if a status needs qualification (meeting held, no verdict yet)."""
    return normalize_status(status) == "meeting_held"


def derive_external_status(
    config: dict,
    reply_category: Optional[str] = None,
    internal_status: Optional[str] = None,
) -> Optional[str]:
    """
    Derive client-facing external status from project config.

    Priority:
      1. internal_status_mapping (meeting stages are most specific)
      2. category_mapping (from AI reply classification)
      3. default_status
    """
    if not config:
        return None

    # Priority 1: internal status → external
    if internal_status:
        mapping = config.get("internal_status_mapping", {})
        ext = mapping.get(normalize_status(internal_status))
        if ext:
            return ext

    # Priority 2: reply category → external
    if reply_category:
        mapping = config.get("category_mapping", {})
        if reply_category in mapping:
            ext = mapping[reply_category]
            if ext is not None:  # None means "don't change"
                return ext

    # Priority 3: default
    return config.get("default_status")
