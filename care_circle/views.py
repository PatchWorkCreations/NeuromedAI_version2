"""
TODO: invite flow (create CareCircle + CareCircleMember, send invite email
in the member's preferred_language) and the async digest delivery job.
Both depend on the translation-vendor decision in ARCHITECTURE.md § Open
decisions — the models and the relationship they express don't.

Gate this whole app behind settings.ENABLE_CARE_CIRCLE until the
translation vendor is chosen — see neuromed_v2/settings.py.
"""
