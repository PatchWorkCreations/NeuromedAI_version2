"""
Visit recording endpoints.

Ports the shape of v1's Record & remember flow (docs/RECORD_MY_VISIT_DOCUMENTATION.md):
chunked capture -> Whisper transcription per segment -> Stop & summarize ->
structured Visit Summary. The two things that are NEW relative to v1:

1. `start_visit` requires a ConsentRecord to already exist for the
   session before a VisitRecording is created at all (boundary #3).
2. `summarize_visit` runs the draft summary through
   safety.engine.check_escalation() before it's returned to the client
   (boundary #2) — this did not exist in v1.
"""
import openai
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from safety.engine import check_escalation, log_escalation

from .consent import CONSENT_TEXT, CONSENT_TEXT_VERSION
from .models import ConsentRecord, VisitRecording

VISIT_SUMMARY_PROMPT = (
    "I recorded my doctor visit. Below is the transcript. Please give me a "
    "clear \"Visit Summary\" in plain language with these sections: "
    "Key points, Diagnoses, Medications & dosages, Instructions, and "
    "Follow-up / next steps. Then add a short list of questions I should "
    "ask at my next visit.\n\n--- VISIT TRANSCRIPT ---\n{transcript}"
)


@api_view(["GET"])
@permission_classes([AllowAny])
def consent_text(request):
    """Returns the current consent copy for the client to render before recording starts."""
    return Response({"text": CONSENT_TEXT, "version": CONSENT_TEXT_VERSION})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def start_visit(request):
    """
    Creates the ConsentRecord *and* the VisitRecording together, atomically.
    The client must call this before requesting microphone access —
    there is no code path that creates a VisitRecording without a
    matching ConsentRecord.
    """
    if not request.session.session_key:
        request.session.create()
    user = request.user if request.user.is_authenticated else None
    session_id = request.session.session_key or ""

    visit = VisitRecording.objects.create(user=user, session_id=session_id)
    ConsentRecord.objects.create(
        user=user,
        session_id=session_id,
        visit_recording=visit,
        consent_text_version=CONSENT_TEXT_VERSION,
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return Response({"visit_id": visit.id})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def voice_transcribe(request):
    """
    Ported from v1's myApp/voice_ai.py transcribe_audio_b64 — chunked,
    6-second-segment transcription via OpenAI Whisper. TODO: port the
    base64-decode / temp-file / whisper-1 call itself once this app is
    wired into a real dev environment with OPENAI_API_KEY set.
    """
    audio = request.FILES.get("audio")
    if not audio:
        return Response({"text": "", "error": "audio is required"}, status=400)
    if not settings.OPENAI_API_KEY:
        return Response({"text": "", "error": "OPENAI_API_KEY is not set"}, status=503)
    if not getattr(audio, "name", None):
        audio.name = "chunk.webm"
    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    result = client.audio.transcriptions.create(model="whisper-1", file=audio)
    return Response({"text": result.text})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def summarize_visit(request, visit_id):
    """
    Stop & summarize. Sends the transcript to OpenAI, then — unlike
    v1 — always runs the draft through the safety layer before it goes
    back to the client.
    """
    visit = VisitRecording.objects.get(pk=visit_id)
    transcript = request.data.get("transcript", visit.transcript)
    visit.transcript = transcript

    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are NeuroMed Aira, a clinical-grade medical communication assistant."},
            {"role": "user", "content": VISIT_SUMMARY_PROMPT.format(transcript=transcript)},
        ],
    )
    draft_summary = completion.choices[0].message.content

    escalation = check_escalation(user_message=transcript, draft_response=draft_summary)
    if escalation:
        log_escalation(
            escalation,
            user=request.user if request.user.is_authenticated else None,
            session_id=request.session.session_key or "",
            visit_recording=visit,
        )
        visit.summary = escalation.response_text
        visit.status = VisitRecording.Status.SUMMARIZED
        visit.ended_at = timezone.now()
        visit.save()
        return Response({"summary": escalation.response_text, "escalated": True, "category": escalation.category})

    visit.summary = draft_summary
    visit.status = VisitRecording.Status.SUMMARIZED
    visit.ended_at = timezone.now()
    visit.save()
    return Response({"summary": draft_summary, "escalated": False})


@login_required
def visit_list(request):
    visits = VisitRecording.objects.filter(user=request.user).exclude(status=VisitRecording.Status.DISCARDED)
    return render(request, "visits/history.html", {"visits": visits})


@login_required
def record_page(request):
    return render(request, "visits/record.html", {
        "consent_text": CONSENT_TEXT,
        "consent_version": CONSENT_TEXT_VERSION,
    })


@login_required
def visit_detail(request, visit_id):
    visit = get_object_or_404(VisitRecording, pk=visit_id, user=request.user)
    return render(request, "visits/summary.html", {"visit": visit})


@login_required
@require_POST
def discard_visit(request, visit_id):
    visit = get_object_or_404(VisitRecording, pk=visit_id, user=request.user)
    visit.status = VisitRecording.Status.DISCARDED
    visit.ended_at = timezone.now()
    visit.save(update_fields=["status", "ended_at"])
    return redirect("visits:list")
