"""
13-Status Lead Funnel State Machine.

Statuses (in funnel order):
  TO_BE_SENT → SENT → [AI classifies reply] →
    INTERESTED → NEGOTIATING_MEETING → SCHEDULED →
      MEETING_HELD → QUALIFIED | NOT_QUALIFIED
      MEETING_NO_SHOW → SCHEDULED (reschedule) | NOT_INTERESTED
      MEETING_RESCHEDULED → SCHEDULED (new date)
    NOT_INTERESTED (terminal)
    OOO → INTERESTED (after follow-up)
    UNSUBSCRIBED (terminal, global blacklist)

Rules:
  - Forward-only: can't go backwards in the funnel
  - Terminal statuses: NOT_INTERESTED, NOT_QUALIFIED, UNSUBSCRIBED — no transitions out
  - OOO is the only exception: can transition to INTERESTED after follow-up
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
TERMINAL = {"not_interested", "not_qualified", "unsubscribed"}

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
    "ooo": {"interested", "not_interested", "unsubscribed"},
    "negotiating_meeting": {"scheduled", "not_interested", "unsubscribed"},
    "scheduled": {
        "meeting_held", "meeting_no_show", "meeting_rescheduled",
        "not_interested", "unsubscribed",
    },
    "meeting_held": {"qualified", "not_qualified"},
    "meeting_no_show": {"scheduled", "not_interested"},
    "meeting_rescheduled": {"scheduled"},
    # Terminal — no transitions out
    "not_interested": set(),
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
