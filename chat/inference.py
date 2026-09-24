"""
Tone inference and response-mode classification.

Reconstructed from v1's documented behavior (docs/TONE_INFERENCE_AND_CHAT_FLOW.md
and mobile_api/ALL_PROMPTS_REFERENCE.md) rather than ported byte-for-byte —
v1's exact keyword lists live inside myApp/views.py, which wasn't pulled
into this session verbatim. The *order* of checks and the *categories*
below match the documented design exactly; the specific keyword lists are
a reasonable reconstruction and should be tightened against real pilot
transcripts (see the roadmap's Phase 2), same as the safety engine's terms.
"""

CLINICAL_TERMS = [
    "soap note", "differential", "rounds", "chart note", "assessment and plan",
    "attending", "resident physician", "provider note", "clinical impression",
]
EMOTIONAL_SUPPORT_TERMS = [
    "anxious", "anxiety", "scared", "overwhelmed", "panic", "can't sleep",
    "cant sleep", "worried sick", "terrified", "stressed out", "freaking out",
]
FAITH_TERMS = [
    "pray", "prayer", "scripture", "bible", "spiritual guidance", "blessing",
]
GERIATRIC_TERMS = [
    "elderly", "my grandmother", "my grandfather", "senior citizen",
    "nursing home", "dementia", "alzheimer", "fall risk", "aging parent",
]
CAREGIVER_TERMS = [
    "my mom", "my dad", "my mother", "my father", "my husband", "my wife",
    "my spouse", "caring for", "i'm a caregiver", "im a caregiver",
]

# Order matters — first match wins, matching v1's documented precedence.
_ORDERED_CHECKS = [
    ("Clinical", CLINICAL_TERMS),
    ("EmotionalSupport", EMOTIONAL_SUPPORT_TERMS),
    ("Faith", FAITH_TERMS),
    ("Geriatric", GERIATRIC_TERMS),
    ("Caregiver", CAREGIVER_TERMS),
]


def infer_use_case(message: str, has_files: bool = False) -> str:
    """Per-message tone inference. Runs only when the client sends no explicit tone."""
    if not message:
        return "PlainClinical"
    lowered = message.lower()
    for tone, terms in _ORDERED_CHECKS:
        if any(term in lowered for term in terms):
            return tone
    return "PlainClinical"


def classify_mode(message: str, has_files: bool = False) -> str:
    """
    QUICK: one short symptom (<12 words), no file.
    EXPLAIN: a general question, no file.
    FULL: any file/image, or a detailed/multi-part message.
    """
    if has_files:
        return "FULL"

    word_count = len(message.split())
    detail_signals = message.count(",") + message.count(".") + message.count(";")

    if word_count > 40 or detail_signals >= 3:
        return "FULL"
    if word_count <= 12:
        return "QUICK"
    return "EXPLAIN"
