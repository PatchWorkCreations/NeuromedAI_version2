"""
Document upload + list.

Stores extracted text on UploadedDocument. Binary media storage is still
open (ARCHITECTURE.md) — this path must succeed without it.
"""
import io
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import UploadedDocument

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB


def _extension(name: str) -> str:
    name = (name or "").lower().strip()
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[-1]


def _extract_text(uploaded) -> str:
    name = (uploaded.name or "").lower()
    data = uploaded.read()
    try:
        uploaded.seek(0)
    except Exception:
        pass

    try:
        if name.endswith(".pdf"):
            import fitz

            doc = fitz.open(stream=data, filetype="pdf")
            try:
                return "\n".join(page.get_text() for page in doc).strip()
            finally:
                doc.close()

        if name.endswith(".docx"):
            import docx

            document = docx.Document(io.BytesIO(data))
            return "\n".join(p.text for p in document.paragraphs).strip()

        if name.endswith((".png", ".jpg", ".jpeg")):
            try:
                import pytesseract
                from PIL import Image

                text = pytesseract.image_to_string(Image.open(io.BytesIO(data)))
                return (text or "").strip()
            except Exception as exc:
                logger.info("Image OCR unavailable or failed: %s", exc)
                return ""

        if name.endswith(".txt"):
            return data.decode("utf-8", errors="ignore").strip()

        # Unknown text-like fallback
        return data.decode("utf-8", errors="ignore").strip()
    except Exception:
        logger.exception("Document text extraction failed for %s", name)
        return ""


@login_required
def document_list(request):
    if request.method == "POST":
        uploaded = request.FILES.get("file")
        if not uploaded:
            messages.error(request, "Choose a file to upload.")
            return redirect("documents:list")

        ext = _extension(uploaded.name)
        if ext not in ALLOWED_EXTENSIONS:
            messages.error(
                request,
                "That file type isn’t supported. Use PDF, Word (.docx), text, PNG, or JPG.",
            )
            return redirect("documents:list")

        if uploaded.size and uploaded.size > MAX_UPLOAD_BYTES:
            messages.error(request, "That file is too large. Please keep uploads under 15 MB.")
            return redirect("documents:list")

        kind = request.POST.get("kind") or UploadedDocument.Kind.OTHER
        if kind not in UploadedDocument.Kind.values:
            kind = UploadedDocument.Kind.OTHER

        source = (request.POST.get("source_institution") or "").strip()[:255]
        extracted = _extract_text(uploaded)

        UploadedDocument.objects.create(
            user=request.user,
            kind=kind,
            source_institution=source,
            extracted_text=extracted,
        )

        if extracted:
            messages.success(request, "Document uploaded. Here’s what we could read from it.")
        elif ext in {".png", ".jpg", ".jpeg"}:
            messages.success(
                request,
                "Image uploaded to your timeline. Text couldn’t be read from it yet — try a PDF or Word file if you need a searchable note.",
            )
        else:
            messages.success(
                request,
                "Document uploaded. We couldn’t pull text out of this file yet, but it’s on your timeline.",
            )
        return redirect("documents:list")

    docs = UploadedDocument.objects.filter(user=request.user)
    return render(
        request,
        "documents/list.html",
        {"documents": docs, "kinds": UploadedDocument.Kind.choices},
    )


@login_required
def document_detail(request, document_id):
    document = get_object_or_404(UploadedDocument, pk=document_id, user=request.user)
    return render(request, "documents/detail.html", {"document": document})


@login_required
@require_POST
def document_delete(request, document_id):
    document = get_object_or_404(UploadedDocument, pk=document_id, user=request.user)
    document.delete()
    messages.success(request, "Document removed from your timeline.")
    return redirect("documents:list")
