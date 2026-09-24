"""
Rule-based escalation checks.

This is deliberately NOT an LLM call. It's a fast, deterministic, fully
auditable pass that runs on every user message and every draft AI response
before either one is allowed to reach a "the model just answers" path.
Keep it that way — see CLAUDE.md boundary #2.

Usage:

    from safety.engine import check_escalation

    result = check_escalation(user_message=user_message, draft_response=draft_response)
    if result:
        log_escalation(result, user=..., chat_session=...)
        return build_escalation_reply(result)
    # otherwise proceed with the normal draft_response

The term lists below are a starting vocabulary carried over from v1's
prompt phrasing (ALL_PROMPTS_REFERENCE.md) — they were never enforced in
code before. Expand them from real pilot transcripts (see the roadmap's
Phase 2: "tighten the escalation policy against real pilot transcripts,
not hypotheticals") rather than guessing exhaustively up front.
"""
from dataclasses import dataclass, field
from typing import Optional

from .models import EscalationCategory

MEDICATION_STOP_START_TERMS = [
    "stop taking", "stop my", "should i stop", "quit taking",
    "start taking", "double my dose", "skip a dose", "skip my dose",
    "stop the medication", "off my medication", "discontinue",
]

SEVERE_INTERACTION_TERMS = [
    "drug interaction", "interact with", "mix with alcohol",
    "take together", "combine with", "overdose", "too much of",
]

EMERGENCY_SIGN_TERMS = [
    "chest pain", "can't breathe", "cannot breathe", "difficulty breathing",
    "severe bleeding", "uncontrolled bleeding", "stroke", "face drooping",
    "slurred speech", "suicidal", "want to die", "severe allergic reaction",
    "anaphylaxis", "unconscious", "seizure", "911", "emergency room",
]

_CATEGORY_TERMS = {
    EscalationCategory.MEDICATION_STOP_START: MEDICATION_STOP_START_TERMS,
    EscalationCategory.SEVERE_INTERACTION: SEVERE_INTERACTION_TERMS,
    EscalationCategory.EMERGENCY_SIGN: EMERGENCY_SIGN_TERMS,
}

# Shown to the user verbatim — keep this in sync with DESIGN.md § The
# escalation moment: calm, accent-colored, never alarm-red styling, and the
# "contact your doctor" action is the visually primary element.
_RESPONSE_TEXT = {
    EscalationCategory.MEDICATION_STOP_START: (
        "This involves starting or stopping a medication — that's a decision "
        "to make with your doctor, not something I can guide you through here. "
        "Please contact your doctor's office before changing anything."
    ),
    EscalationCategory.SEVERE_INTERACTION: (
        "This sounds like it could involve a serious interaction between "
        "medications or substances. Please check with your doctor or "
        "pharmacist before continuing, or call your local emergency number "
        "if you're feeling unwell right now."
    ),
    EscalationCategory.EMERGENCY_SIGN: (
        "What you're describing could be a medical emergency. Please call "
        "your local emergency number or go to the nearest emergency room "
        "right now — this isn't something to wait on an AI response for."
    ),
}


@dataclass
class EscalationResult:
    category: str
    matched_terms: list = field(default_factory=list)
    trigger_text: str = ""
    response_text: str = ""


def _scan(text: str, terms: list) -> list:
    lowered = text.lower()
    return [term for term in terms if term in lowered]


def check_escalation(
    user_message: str = "",
    draft_response: str = "",
) -> Optional[EscalationResult]:
    """
    Checks both the user's message and the model's draft response against
    every escalation category. Returns the first match (categories are
    checked in the order below deliberately — emergency signs take
    priority over the other two if a message somehow matches more than
    one) or None if nothing matched.
    """
    combined = f"{user_message}\n{draft_response}"

    for category in (
        EscalationCategory.EMERGENCY_SIGN,
        EscalationCategory.MEDICATION_STOP_START,
        EscalationCategory.SEVERE_INTERACTION,
    ):
        matches = _scan(combined, _CATEGORY_TERMS[category])
        if matches:
            return EscalationResult(
                category=category,
                matched_terms=matches,
                trigger_text=combined.strip()[:2000],
                response_text=_RESPONSE_TEXT[category],
            )
    return None


def log_escalation(result: EscalationResult, *, user=None, session_id="", chat_session=None, visit_recording=None):
    """Persists an EscalationEvent. Call this every time check_escalation() matches — no exceptions."""
    from .models import EscalationEvent  # local import avoids circulars at app-load time

    return EscalationEvent.objects.create(
        user=user if user and user.is_authenticated else None,
        session_id=session_id or "",
        chat_session=chat_session,
        visit_recording=visit_recording,
        category=result.category,
        matched_terms=result.matched_terms,
        trigger_text=result.trigger_text,
        response_shown=result.response_text,
    )
