from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import UploadedDocument


def _extract_text(uploaded):
    name = (uploaded.name or "").lower()
    data = uploaded.read()
    uploaded.seek(0)
    try:
        if name.endswith(".pdf"):
            import fitz
            doc = fitz.open(stream=data, filetype="pdf")
            return "\n".join(page.get_text() for page in doc)
        if name.endswith(".docx"):
            import io
            import docx
            document = docx.Document(io.BytesIO(data))
            return "\n".join(p.text for p in document.paragraphs)
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


@login_required
def document_list(request):
    if request.method == "POST" and request.FILES.get("file"):
        uploaded = request.FILES["file"]
        UploadedDocument.objects.create(
            user=request.user,
            kind=request.POST.get("kind") or UploadedDocument.Kind.OTHER,
            source_institution=request.POST.get("source_institution") or "",
            extracted_text=_extract_text(uploaded),
        )
        return redirect("documents:list")
    docs = UploadedDocument.objects.filter(user=request.user)
    return render(request, "documents/list.html", {"documents": docs, "kinds": UploadedDocument.Kind.choices})
