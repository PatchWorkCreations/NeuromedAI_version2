"""
Chat send endpoint.

Ports v1's send_chat (myApp/views.py + mobile_api/views.py), but fixes the
bug documented in docs/TONE_INFERENCE_AND_CHAT_FLOW.md: mobile_api always
defaulted `tone` to "plain_clinical" before it reached the inference layer,
so server-side tone inference never actually fired for mobile clients. Here,
inference only runs when the client sends no tone at all (or explicitly
sends "auto") — an explicit client-selected tone always wins.

Every draft response is passed through safety.engine.check_escalation()
before it's saved or returned — boundary #2 in CLAUDE.md. This governs
plain chat exactly the same way visits.views.summarize_visit governs visit
summaries; there is one safety layer, not two.
"""
import openai
from django.conf import settings
from django.contrib.auth.decorators import login_required
from datetime import timedelta

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from safety.engine import check_escalation, log_escalation

from documents.ingest import UploadRejected, image_data_url
from documents.ingest import check as check_upload
from documents.ingest import ingest as ingest_upload

from .context import build_patient_context
from .guidance import GUIDE_PROMPT, SHARED_IMAGE_NOTE, build_starters, ensure_open_ending, split_follow_ups
from .inference import classify_mode, infer_use_case
from .models import ChatMessage, ChatSession
from .prompts import build_system_prompt, normalize_tone

NO_TONE_SENTINELS = {"", "auto", "automatic", None}
MAX_CHAT_FILES = 3
SHARED_TEXT_CHARS = 8000   # per document, in the turn it was shared
HISTORY_TEXT_CHARS = 1500  # per document, when it comes up again later in the chat


def _clip(text, limit):
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " […]"


def _current_turn(message, docs):
    """The patient's message plus what they shared: photos as images, documents as text."""
    if not docs:
        return message
    parts = [{"type": "text", "text": message or "I've shared a document. Can you help me understand it?"}]
    for d in docs:
        label = f"{d.original_name} ({d.get_kind_display().lower()})"
        if d.is_image:
            url = image_data_url(getattr(d, "_raw_bytes", b""))
            if url:
                parts.append({"type": "text", "text": f"[Photo shared by the patient: {label}]"})
                parts.append({"type": "image_url", "image_url": {"url": url, "detail": "high"}})
            else:
                parts.append({"type": "text", "text": f"[Photo shared: {label}. It couldn't be opened; ask the patient to try a JPG or PNG.]"})
        else:
            body = _clip(d.extracted_text, SHARED_TEXT_CHARS) or "(no readable text could be extracted)"
            parts.append({"type": "text", "text": f"[Document shared by the patient: {label}]\n{body}"})
    return parts


def _history_text(m):
    """Earlier turns stay text-only; a short note keeps shared files in view."""
    content = m.content
    if m.role == ChatMessage.Role.USER:
        notes = []
        for d in m.attachments.all():
            snippet = _clip(d.extracted_text, HISTORY_TEXT_CHARS)
            notes.append(f"[Shared earlier: {d.original_name}]" + (f"\n{snippet}" if snippet else ""))
        if notes:
            content = (content + "\n" + "\n".join(notes)).strip()
    return content or "(shared a file)"


def _attachment_json(d):
    return {
        "id": d.pk,
        "name": d.original_name,
        "is_image": d.is_image,
        "url": reverse("documents:file", args=[d.pk]) if d.has_file else "",
        "detail_url": reverse("documents:detail", args=[d.pk]),
    }


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def send_chat(request):
    data = request.data
    message = (data.get("message") or "").strip()
    files = request.FILES.getlist("files")
    if not message and not files:
        return Response({"error": "message is required"}, status=400)
    if files and not request.user.is_authenticated:
        return Response({"error": "Sign in to share documents with Aira."}, status=403)
    if len(files) > MAX_CHAT_FILES:
        return Response({"error": f"You can share up to {MAX_CHAT_FILES} files at a time."}, status=400)
    for f in files:
        try:
            check_upload(f)
        except UploadRejected as exc:
            return Response({"error": str(exc)}, status=400)

    session_key = data.get("session_id") or request.session.session_key or ""
    care_setting = data.get("care_setting")
    faith_setting = data.get("faith_setting")
    lang = data.get("lang", "en-US")
    has_files = bool(files) or bool(data.get("has_files", False))
    client_tone = data.get("tone")

    user = request.user if request.user.is_authenticated else None
    conversation_id = data.get("conversation_id")
    if user is not None:
        # Signed in: every conversation is its own ChatSession, picked by id.
        # No id means the patient pressed "New chat" (or has never chatted).
        if conversation_id:
            try:
                session = ChatSession.objects.get(pk=int(conversation_id), user=user)
            except (ChatSession.DoesNotExist, TypeError, ValueError):
                return Response({"error": "Conversation not found"}, status=404)
        else:
            session = ChatSession.objects.create(
                user=user, session_id=session_key, tone="PlainClinical", lang=lang,
            )
    else:
        # Guests keep one running conversation per browser session.
        session, _ = ChatSession.objects.get_or_create(
            user=None,
            session_id=session_key,
            defaults={"tone": "PlainClinical", "lang": lang},
        )
    if not session.title:
        session.title = ChatSession.title_from(message or f"Shared {files[0].name}")

    # Explicit client tone always wins. Only infer when none was sent —
    # this is the fix for the mobile default-to-plain_clinical bug.
    if client_tone in NO_TONE_SENTINELS:
        tone = infer_use_case(message, has_files=has_files)
    else:
        tone = normalize_tone(client_tone)

    mode = classify_mode(message, has_files=has_files)
    session.tone = tone
    session.lang = lang
    session.save(update_fields=["title", "tone", "lang", "updated_at"])

    user_msg = ChatMessage.objects.create(session=session, role=ChatMessage.Role.USER, content=message)
    shared_docs = [
        ingest_upload(user, f, source="Shared in Ask Aira", chat_message=user_msg) for f in files
    ]

    system_prompt = build_system_prompt(tone, care_setting, faith_setting, lang)
    patient_context = build_patient_context(user)
    if patient_context:
        system_prompt += "\n\n" + patient_context
    system_prompt += "\n\n" + GUIDE_PROMPT
    if any(d.is_image for d in shared_docs):
        system_prompt += "\n\n" + SHARED_IMAGE_NOTE
    if mode == "QUICK":
        system_prompt += "\n\n(Keep this answer short — a couple of sentences, not a full write-up.)"
    elif mode == "FULL":
        system_prompt += "\n\n(This warrants a fuller, structured response with clear sections.)"

    history = list(
        session.messages.order_by("-created_at")[:20]
    )[::-1]

    if not settings.OPENAI_API_KEY:
        return Response(
            {"error": "OPENAI_API_KEY is not set", "conversation_id": session.pk, "title": session.title,
             "attachments": [_attachment_json(d) for d in shared_docs]},
            status=503,
        )

    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    model_messages = [{"role": "system", "content": system_prompt}]
    for m in history:
        if m.pk == user_msg.pk:
            model_messages.append({"role": "user", "content": _current_turn(message, shared_docs)})
        else:
            model_messages.append({"role": m.role, "content": _history_text(m)})
    completion = client.chat.completions.create(model="gpt-4o", messages=model_messages)
    draft_reply, follow_ups = split_follow_ups(completion.choices[0].message.content or "")
    draft_reply = ensure_open_ending(draft_reply)

    shared_text = "\n".join(d.extracted_text for d in shared_docs if d.extracted_text)
    escalation = check_escalation(
        user_message=(message + "\n" + shared_text).strip(), draft_response=draft_reply,
    )
    if escalation:
        log_escalation(escalation, user=user, session_id=session_key, chat_session=session)
        reply = escalation.response_text
        ChatMessage.objects.create(session=session, role=ChatMessage.Role.ASSISTANT, content=reply)
        # No suggested questions after a safety redirect: the next step is the doctor.
        return Response({
            "reply": reply,
            "tone": tone,
            "mode": mode,
            "escalated": True,
            "category": escalation.category,
            "attachments": [_attachment_json(d) for d in shared_docs],
            "session_id": session_key,
            "conversation_id": session.pk,
            "title": session.title,
        })

    ChatMessage.objects.create(
        session=session, role=ChatMessage.Role.ASSISTANT, content=draft_reply, follow_ups=follow_ups,
    )
    return Response({
        "reply": draft_reply,
        "follow_ups": follow_ups,
        "attachments": [_attachment_json(d) for d in shared_docs],
        "tone": tone,
        "mode": mode,
        "escalated": False,
        "session_id": session_key,
        "conversation_id": session.pk,
        "title": session.title,
    })


def _history_groups(user, now=None):
    """Conversations grouped the way people remember them: today, yesterday, this week, earlier."""
    now = timezone.localtime(now or timezone.now())
    today = now.date()
    labels = ["Today", "Yesterday", "Previous 7 days", "Earlier"]
    buckets = {label: [] for label in labels}
    sessions = ChatSession.objects.filter(user=user, messages__isnull=False).distinct().order_by("-updated_at")[:60]
    for convo in sessions:
        day = timezone.localtime(convo.updated_at).date()
        if day == today:
            key = "Today"
        elif day == today - timedelta(days=1):
            key = "Yesterday"
        elif day > today - timedelta(days=7):
            key = "Previous 7 days"
        else:
            key = "Earlier"
        buckets[key].append(convo)
    return [(label, buckets[label]) for label in labels if buckets[label]]


def _render_chat(request, conversation=None):
    if not request.session.session_key:
        request.session.create()
    messages = list(conversation.messages.prefetch_related("attachments")) if conversation else []
    return render(request, "chat/room.html", {
        "chat_messages": messages,
        "conversation": conversation,
        "history_groups": _history_groups(request.user),
        # ?ask= pre-fills the composer, e.g. from a visit's "Ask Aira" link. Never auto-sent.
        "prefill": "" if conversation else (request.GET.get("ask") or "")[:300],
        "starters": [] if conversation else build_starters(request.user),
    })


@login_required
def chat_page(request):
    """A fresh conversation. It is only saved once the first message is sent."""
    return _render_chat(request)


@login_required
def conversation_page(request, conversation_id):
    conversation = get_object_or_404(ChatSession, pk=conversation_id, user=request.user)
    return _render_chat(request, conversation)


@login_required
@require_POST
def delete_conversation(request, conversation_id):
    conversation = get_object_or_404(ChatSession, pk=conversation_id, user=request.user)
    # Messages go with it. Any EscalationEvent keeps its audit row (FK is SET_NULL).
    conversation.delete()
    return redirect("chat:room")
