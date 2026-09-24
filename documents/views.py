"""
Document upload + list.

Stores extracted text on UploadedDocument. Binary media storage is still
open (ARCHITECTURE.md) — this path must succeed without it.
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import storage
from .ingest import UploadRejected, extension, ingest
from .models import UploadedDocument

logger = logging.getLogger(__name__)

@login_required
def document_list(request):
    if request.method == "POST":
        uploaded = request.FILES.get("file")
        if not uploaded:
            messages.error(request, "Choose a file to upload.")
            return redirect("documents:list")

        ext = extension(uploaded.name)
        try:
            doc = ingest(
                request.user,
                uploaded,
                kind=request.POST.get("kind") or UploadedDocument.Kind.OTHER,
                source=request.POST.get("source_institution") or "",
            )
        except UploadRejected as exc:
            messages.error(request, str(exc))
            return redirect("documents:list")
        extracted = doc.extracted_text

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
    storage.remove(document.file_key)
    document.delete()
    messages.success(request, "Document removed from your timeline.")
    return redirect("documents:list")


@login_required
def document_file(request, document_id):
    """The original file, decrypted for its owner only. Never cached, never public."""
    document = get_object_or_404(UploadedDocument, pk=document_id, user=request.user)
    if not document.file_key:
        raise Http404("No stored file")
    try:
        data = storage.load(document.file_key)
    except storage.StorageError:
        logger.exception("Could not load stored file for document %s", document.pk)
        raise Http404("File unavailable")
    response = HttpResponse(data, content_type=document.content_type or "application/octet-stream")
    disposition = "inline" if request.GET.get("download") != "1" else "attachment"
    safe_name = (document.original_name or "document").replace('"', "")
    response["Content-Disposition"] = f'{disposition}; filename="{safe_name}"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
