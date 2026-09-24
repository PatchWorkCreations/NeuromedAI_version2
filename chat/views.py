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
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from safety.engine import check_escalation, log_escalation

from .inference import classify_mode, infer_use_case
from .models import ChatMessage, ChatSession
from .prompts import build_system_prompt, normalize_tone

NO_TONE_SENTINELS = {"", "auto", "automatic", None}


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def send_chat(request):
    data = request.data
    message = (data.get("message") or "").strip()
    if not message:
        return Response({"error": "message is required"}, status=400)

    session_key = data.get("session_id") or request.session.session_key or ""
    care_setting = data.get("care_setting")
    faith_setting = data.get("faith_setting")
    lang = data.get("lang", "en-US")
    has_files = bool(data.get("has_files", False))
    client_tone = data.get("tone")

    user = request.user if request.user.is_authenticated else None
    session, _ = ChatSession.objects.get_or_create(
        user=user,
        session_id=session_key,
        defaults={"tone": "PlainClinical", "lang": lang},
    )

    # Explicit client tone always wins. Only infer when none was sent —
    # this is the fix for the mobile default-to-plain_clinical bug.
    if client_tone in NO_TONE_SENTINELS:
        tone = infer_use_case(message, has_files=has_files)
    else:
        tone = normalize_tone(client_tone)

    mode = classify_mode(message, has_files=has_files)
    session.tone = tone
    session.lang = lang
    session.save(update_fields=["tone", "lang", "updated_at"])

    ChatMessage.objects.create(session=session, role=ChatMessage.Role.USER, content=message)

    system_prompt = build_system_prompt(tone, care_setting, faith_setting, lang)
    if mode == "QUICK":
        system_prompt += "\n\n(Keep this answer short — a couple of sentences, not a full write-up.)"
    elif mode == "FULL":
        system_prompt += "\n\n(This warrants a fuller, structured response with clear sections.)"

    history = list(
        session.messages.order_by("-created_at")[:20]
    )[::-1]

    if not settings.OPENAI_API_KEY:
        return Response({"error": "OPENAI_API_KEY is not set"}, status=503)

    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt}]
        + [{"role": m.role, "content": m.content} for m in history],
    )
    draft_reply = completion.choices[0].message.content

    escalation = check_escalation(user_message=message, draft_response=draft_reply)
    if escalation:
        log_escalation(escalation, user=user, session_id=session_key, chat_session=session)
        reply = escalation.response_text
        ChatMessage.objects.create(session=session, role=ChatMessage.Role.ASSISTANT, content=reply)
        return Response({
            "reply": reply,
            "tone": tone,
            "mode": mode,
            "escalated": True,
            "category": escalation.category,
            "session_id": session_key,
        })

    ChatMessage.objects.create(session=session, role=ChatMessage.Role.ASSISTANT, content=draft_reply)
    return Response({
        "reply": draft_reply,
        "tone": tone,
        "mode": mode,
        "escalated": False,
        "session_id": session_key,
    })


@login_required
def chat_page(request):
    if not request.session.session_key:
        request.session.create()
    session = ChatSession.objects.filter(
        user=request.user,
    ).order_by("-updated_at").first()
    messages = []
    if session:
        messages = list(session.messages.all())
    return render(request, "chat/room.html", {
        "chat_messages": messages,
        "session": session,
    })
