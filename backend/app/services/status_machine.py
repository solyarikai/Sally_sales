"""
11-Status Lead Funnel State Machine.

Status = funnel stage (what happened), Reply Type = quality of response (how they replied).
These are orthogonal: Status tells you WHERE in the process, Reply Type tells you WHAT they said.

Statuses (in funnel order):
  NEW → SENT → REPLIED → NEGOTIATING_MEETING → CALENDLY_SENT → SCHEDULED →
    MEETING_HELD → QUALIFIED | NOT_QUALIFIED
    MEETING_NO_SHOW | MEETING_RESCHEDULED → SCHEDULED
  UNSUBSCRIBED (terminal, global blacklist)

Rules:
  - Forward-only: can't go backwards in the funnel
  - REPLIED = "lead responded" (details in Reply Type column)
  - Terminal statuses: NOT_QUALIFIED, UNSUBSCRIBED — no transitions out
  - AI classification maps ALL reply categories to REPLIED (except meeting_request → NEGOTIATING_MEETING)
"""
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# ── All valid statuses ──

STATUSES = [
    "new",
    "sent",
    "replied",
    "unsubscribed",
    "negotiating_meeting",
    "calendly_sent",
    "scheduled",
    "meeting_held",
    "meeting_no_show",
    "meeting_rescheduled",
    "qualified",
    "not_qualified",
]

# Terminal statuses — no transitions out
TERMINAL = {"not_qualified", "unsubscribed"}

# Funnel rank for forward-only enforcement
STATUS_RANK = {
    "new": 0,
    "sent": 1,
    "replied": 2,
    "unsubscribed": 2,
    "negotiating_meeting": 3,
    "calendly_sent": 3,
    "scheduled": 4,
    "meeting_held": 5,
    "meeting_no_show": 5,
    "meeting_rescheduled": 5,
    "qualified": 6,
    "not_qualified": 6,
}

# ── Valid transitions (from → set of allowed targets) ──

VALID_TRANSITIONS = {
    "new": {"sent"},
    "sent": {
        "replied", "unsubscribed",
        "negotiating_meeting",  # direct if reply is meeting request
    },
    "replied": {"negotiating_meeting", "unsubscribed"},
    "negotiating_meeting": {"calendly_sent", "scheduled", "unsubscribed"},
    "calendly_sent": {"scheduled", "negotiating_meeting", "unsubscribed"},
    "scheduled": {
        "meeting_held", "meeting_no_show", "meeting_rescheduled",
        "unsubscribed",
    },
    "meeting_held": {"qualified", "not_qualified", "unsubscribed"},
    "meeting_no_show": {"scheduled", "unsubscribed"},
    "meeting_rescheduled": {"scheduled", "unsubscribed"},
    # Terminal — no transitions out
    "not_qualified": set(),
    "unsubscribed": set(),
    "qualified": set(),
}

# ── AI classification → CRM status mapping ──
# All reply categories map to "replied" — the detail lives in Reply Type.
# Exception: meeting_request → negotiating_meeting (they're asking for a call).

AI_CATEGORY_TO_STATUS = {
    "interested": "replied",
    "meeting_request": "negotiating_meeting",
    "not_interested": "replied",
    "out_of_office": "replied",
    "unsubscribe": "unsubscribed",
    "question": "replied",
    "wrong_person": "replied",
    "other": "replied",
}

# ── Legacy status migration (old statuses → new) ──

LEGACY_STATUS_MAP = {
    "lead": "new",
    "to_be_sent": "new",
    "contacted": "sent",
    "touched": "sent",
    "replied": "replied",
    "interested": "replied",
    "not_interested": "replied",
    "warm": "replied",
    "ooo": "replied",
    "out_of_office": "replied",
    "wrong_person": "replied",
    "scheduling": "negotiating_meeting",
    "meeting_booked": "scheduled",
}


def normalize_status(status: Optional[str]) -> str:
    """Map legacy/unknown status to the 11-status system."""
    if not status:
        return "new"
    s = status.strip().lower()
    if s in STATUS_RANK:
        return s
    return LEGACY_STATUS_MAP.get(s, "new")


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
    return AI_CATEGORY_TO_STATUS.get(category, "replied")


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
        "replied", "negotiating_meeting", "scheduled",
        "meeting_held", "meeting_rescheduled",
    }


def is_meeting_stage(status: str) -> bool:
    """Check if a status is in the meetings zone."""
    return normalize_status(status) in {
        "negotiating_meeting", "calendly_sent", "scheduled", "meeting_held",
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
