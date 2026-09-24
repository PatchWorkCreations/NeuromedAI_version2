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

    class Meta:
        ordering = ["-uploaded_at"]
