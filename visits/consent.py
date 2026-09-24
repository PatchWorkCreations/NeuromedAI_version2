"""
The current consent copy, versioned. Bump CONSENT_TEXT_VERSION any time
the wording changes materially — ConsentRecord.consent_text_version
stores which version a given patient actually saw, so the audit trail
stays meaningful even after the copy is edited later.
"""

CONSENT_TEXT_VERSION = "v1"

CONSENT_TEXT = (
    "Everyone in the room should agree to be recorded. This recording helps "
    "you remember what was said — it is transcribed to build your Visit "
    "Summary and isn't shared without your say. You can stop at any time."
)
