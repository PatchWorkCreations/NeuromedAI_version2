"""
One Aira answer, packaged for keeping: the printable page and the "Email me
this" message both render from build_export(), so what a patient prints and
what lands in their inbox are the same thing.

Model text is never trusted as HTML. format_answer() escapes every line
before it adds the few tags it knows (headings, lists, paragraphs).
"""
import re

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

from .models import ChatMessage

SAFETY_FOOTER = (
    "Aira explains health information; it does not replace your doctor. "
    "In an emergency call your local emergency number."
)

_HEADING = re.compile(r"^[#*\s]*([A-Za-z&/ ,’'()-]{2,48}?)[:*#\s]*$")
_BULLET = re.compile(r"^[-*•]\s+(.*)$")
_NUMBERED = re.compile(r"^\d{1,2}[.)]\s+(.*)$")


def _clean(text):
    return text.replace("**", "").replace("__", "").strip()


def format_answer(text):
    """Aira's reply as safe HTML: headings, bulleted and numbered lists, paragraphs."""
    if not text:
        return ""
    out, para, items = [], [], []
    list_tag = None

    def flush():
        nonlocal list_tag
        if para:
            out.append("<p>" + "<br>".join(para) + "</p>")
            para.clear()
        if items:
            out.append(f"<{list_tag}>" + "".join(f"<li>{i}</li>" for i in items) + f"</{list_tag}>")
            items.clear()
        list_tag = None

    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            flush()
            continue
        bullet, numbered = _BULLET.match(stripped), _NUMBERED.match(stripped)
        if bullet or numbered:
            tag = "ul" if bullet else "ol"
            if para or (items and list_tag != tag):
                flush()
            list_tag = tag
            items.append(escape(_clean((bullet or numbered).group(1))))
            continue
        clean = escape(_clean(stripped.lstrip("#").strip()))
        if _HEADING.match(stripped) and not clean.endswith((".", "!", "?")):
            flush()
            out.append(f"<h3>{clean.rstrip(':')}</h3>")
        else:
            if items:
                flush()
            para.append(escape(_clean(stripped)))
    flush()
    return mark_safe("".join(out))


def plain_answer(text):
    return "\n".join(_clean(line.lstrip("#").strip()) for line in (text or "").splitlines()).strip()


def doctor_questions(message):
    """Questions listed in the answer itself, then Aira's suggested follow-ups, without repeats."""
    found = []
    for raw in (message.content or "").splitlines():
        match = _BULLET.match(raw.strip()) or _NUMBERED.match(raw.strip())
        if match:
            line = _clean(match.group(1))
            if line.endswith("?"):
                found.append(line)
    found += [q.strip() for q in (message.follow_ups or []) if isinstance(q, str) and q.strip()]
    seen, unique = set(), []
    for q in found:
        key = q.lower()
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique


def get_owned_answer(user, message_id):
    """An Aira answer from one of this user's own conversations, or 404."""
    return get_object_or_404(
        ChatMessage.objects.select_related("session"),
        pk=message_id, role=ChatMessage.Role.ASSISTANT, session__user=user,
    )


def absolute_url(path, request=None):
    base = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    if base:
        return base + path
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def build_export(message, request=None):
    session = message.session
    question = (
        session.messages.filter(role=ChatMessage.Role.USER, pk__lt=message.pk).order_by("-pk").first()
    )
    return {
        "message": message,
        "title": session.display_title,
        "question": question.content if question else "",
        "answer_html": format_answer(message.content),
        "answer_text": plain_answer(message.content),
        "doctor_questions": doctor_questions(message),
        "prepared_on": timezone.localtime(message.created_at).date(),
        "conversation_url": absolute_url(reverse("chat:conversation", args=[session.pk]), request),
        "logo_url": absolute_url(static("img/aira-wordmark.png"), request),
        "safety_footer": SAFETY_FOOTER,
    }
