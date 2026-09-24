from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import FileResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import TemplateView

BASE_DIR = Path(__file__).resolve().parent.parent


class HomeView(TemplateView):
    template_name = "home.html"

    def dispatch(self, request, *args, **kwargs):
        # Signed-in patients land in the product, not the marketing page.
        if request.user.is_authenticated:
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)


@login_required
def dashboard(request):
    """Signed-in home: where you are, and the one thing worth doing next."""
    from chat.models import ChatMessage
    from documents.models import UploadedDocument
    from visits.models import VisitRecording

    user = request.user
    visits_qs = VisitRecording.objects.filter(user=user).exclude(
        status=VisitRecording.Status.DISCARDED
    )
    docs_qs = UploadedDocument.objects.filter(user=user)
    recent_visits = list(visits_qs[:3])
    recent_docs = list(docs_qs[:3])
    visit_count = visits_qs.count()
    doc_count = docs_qs.count()
    question_count = ChatMessage.objects.filter(
        session__user=user, role=ChatMessage.Role.USER
    ).count()

    latest = recent_visits[0] if recent_visits else None
    now = timezone.now()
    if latest is None:
        next_step = {"kind": "first_visit"}
    elif latest.status == VisitRecording.Status.RECORDING:
        next_step = {"kind": "unfinished", "visit": latest}
    elif latest.summary and (now - latest.started_at).days <= 14:
        next_step = {"kind": "review", "visit": latest}
    else:
        next_step = {"kind": "upcoming", "visit": latest}

    checklist = [
        {"label": "Create your account", "done": True, "url": None},
        {"label": "Record your first visit", "done": visit_count > 0, "url": "visits:record",
         "hint": "Consent first, then the microphone."},
        {"label": "Ask Aira a question", "done": question_count > 0, "url": "chat:room",
         "hint": "About a visit, a word, or a worry."},
        {"label": "Add a lab result or discharge paper", "done": doc_count > 0, "url": "documents:list",
         "hint": "PDF, Word, or a photo."},
    ]
    done = sum(1 for item in checklist if item["done"])

    return render(request, "dashboard.html", {
        "today": timezone.localtime(now),
        "next_step": next_step,
        "recent_visits": recent_visits,
        "recent_docs": recent_docs,
        "visit_count": visit_count,
        "doc_count": doc_count,
        "question_count": question_count,
        "checklist": checklist,
        "checklist_done": done,
        "checklist_total": len(checklist),
        "checklist_pct": round(done * 100 / len(checklist)),
        "onboarding_complete": done == len(checklist),
    })


def web_manifest(request):
    """Serve the PWA manifest with resolved static icon URLs (works in prod)."""
    icon_192 = staticfiles_storage.url("img/icons/icon-192.png")
    icon_512 = staticfiles_storage.url("img/icons/icon-512.png")
    payload = {
        "name": "Aira — NeuroMed",
        "short_name": "Aira",
        "description": (
            "Understand, remember, and act on what happened at the doctor "
            "— for patients and families."
        ),
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait-primary",
        "background_color": "#0b2545",
        "theme_color": "#0b2545",
        "lang": "en",
        "categories": ["health", "medical", "lifestyle"],
        "icons": [
            {"src": icon_192, "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": icon_512, "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": icon_512, "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    response = JsonResponse(payload)
    response["Content-Type"] = "application/manifest+json"
    return response


def service_worker(request):
    path = BASE_DIR / "static" / "js" / "sw.js"
    response = FileResponse(path.open("rb"), content_type="application/javascript; charset=utf-8")
    # Allow controlling the whole origin, not only /static/.
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response
