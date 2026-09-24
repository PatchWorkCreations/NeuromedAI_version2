"""
What Aira knows about the patient's own care when they chat.

Every chat reply gets a short, capped briefing built from the patient's
own Aira records: their most recent visit summaries and uploaded
documents. Without it, "explain my last visit" has nothing to work from.

Scope and safety:
- Only the signed-in user's own records; guests get nothing.
- Discarded visits are excluded.
- Capped in size so a long history can't crowd out the conversation.
- This only adds context. The reply still goes through
  safety.engine.check_escalation() in chat.views.send_chat (boundary #2).
- The records were already produced by or sent to the same vendor
  (Whisper/GPT summaries, extracted document text), so this adds no new
  vendor (boundary #5).
"""
from django.utils import timezone

MAX_VISITS = 3
MAX_DOCUMENTS = 3
VISIT_CHARS = 1800
DOCUMENT_CHARS = 1200


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + " […]"


def _when(dt) -> str:
    return timezone.localtime(dt).strftime("%A, %d %B %Y").replace(" 0", " ")


def build_patient_context(user) -> str:
    if user is None or not getattr(user, "is_authenticated", False):
        return ""

    from documents.models import UploadedDocument
    from visits.models import VisitRecording

    visits = list(
        VisitRecording.objects.filter(user=user)
        .exclude(status=VisitRecording.Status.DISCARDED)
        .exclude(summary="")
        .order_by("-started_at")[:MAX_VISITS]
    )
    docs = list(UploadedDocument.objects.filter(user=user).order_by("-uploaded_at")[:MAX_DOCUMENTS])

    lines = [
        "PATIENT RECORDS",
        "Below are this patient's own records saved in Aira. Use them whenever the "
        "patient refers to their visit, their summary, their results, or 'what the "
        "doctor said'. Say which visit or document you mean by its date. Explain in "
        "plain words. Never invent details that are not written here; if something "
        "isn't in the records, say so and suggest asking their doctor.",
        f"Today is {_when(timezone.now())}.",
        "",
    ]

    if visits:
        lines.append(f"Recorded visits (newest first, {len(visits)} shown):")
        for i, v in enumerate(visits, 1):
            label = "most recent visit" if i == 1 else "earlier visit"
            lines.append(f"--- Visit {i} ({label}) on {_when(v.started_at)} ---")
            lines.append(_clip(v.summary, VISIT_CHARS))
            lines.append("")
    else:
        lines.append(
            "Recorded visits: none yet. If the patient asks about 'my visit', explain "
            "kindly that no visit has been recorded in Aira yet, and that they can "
            "use 'Record a visit' at their next appointment, or paste what they have."
        )
        lines.append("")

    if docs:
        lines.append(f"Uploaded documents (newest first, {len(docs)} shown):")
        for d in docs:
            source = d.source_institution or "source not noted"
            lines.append(f"--- {d.get_kind_display()} from {source}, added {_when(d.uploaded_at)} ---")
            text = _clip(d.extracted_text, DOCUMENT_CHARS)
            lines.append(text or "(no readable text was extracted from this file)")
            lines.append("")

    lines.append(
        "SCOPE: You help with health, care, visits, medicines and results. If the "
        "patient drifts to unrelated topics, answer briefly and kindly, then steer "
        "back to how you can help with their care."
    )
    return "\n".join(lines).strip()
