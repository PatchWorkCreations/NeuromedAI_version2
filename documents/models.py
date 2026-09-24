"""
Document ingestion — the OCR/parsing pipeline (PyMuPDF, python-docx,
pytesseract) is a straight port from v1 (see Keep, Rework, Cut). The
UploadedDocument model below is new: it's what lets multiple documents
from different hospitals/EHRs stitch into one timeline per patient,
which v1 never modeled explicitly.
"""
from django.conf import settings
from django.db import models


class UploadedDocument(models.Model):
    class Kind(models.TextChoices):
        LAB_RESULT = "lab_result", "Lab result"
        DISCHARGE_SUMMARY = "discharge_summary", "Discharge summary"
        PRESCRIPTION = "prescription", "Prescription"
        IMAGING = "imaging", "Imaging"
        OTHER = "other", "Other"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    session_id = models.CharField(max_length=255, blank=True)
    kind = models.CharField(max_length=32, choices=Kind.choices, default=Kind.OTHER)
    source_institution = models.CharField(
        max_length=255, blank=True,
        help_text="Freeform — which hospital/portal this came from, if known. Powers the cross-institution timeline.",
    )
    extracted_text = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # The original file, encrypted at rest (see documents/storage.py). Empty for
    # documents uploaded before file storage existed; those only kept their text.
    file_key = models.CharField(max_length=255, blank=True)
    original_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    chat_message = models.ForeignKey(
        "chat.ChatMessage", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="attachments",
        help_text="Set when the file was shared in an Ask Aira conversation.",
    )

    class Meta:
        ordering = ["-uploaded_at"]

    @property
    def title(self) -> str:
        """A kind like "Lab result", or the file name for things shared without a kind."""
        if self.kind == self.Kind.OTHER and self.original_name:
            return self.original_name
        return self.get_kind_display()

    @property
    def has_file(self) -> bool:
        return bool(self.file_key)

    @property
    def is_image(self) -> bool:
        return self.content_type.startswith("image/")
