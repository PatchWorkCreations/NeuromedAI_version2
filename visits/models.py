"""
Visit recording + consent.

See CLAUDE.md boundary #3: no audio capture path may skip writing a
ConsentRecord first. A ConsentRecord is created the moment the patient
confirms the consent screen (DESIGN.md § The consent moment) — before
getUserMedia() is ever called on the client.
"""
from django.conf import settings
from django.db import models


class VisitRecording(models.Model):
    class Status(models.TextChoices):
        RECORDING = "recording", "Recording"
        SUMMARIZED = "summarized", "Summarized"
        DISCARDED = "discarded", "Discarded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    session_id = models.CharField(max_length=255, blank=True)  # guest support

    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    transcript = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECORDING)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Visit {self.pk} ({self.status}) — {self.started_at:%Y-%m-%d}"


class ConsentRecord(models.Model):
    """
    Written before the microphone opens — see module docstring. One
    VisitRecording can have more than one ConsentRecord row (e.g. a
    caregiver confirms on the patient's behalf, or consent is re-confirmed
    after a pause) — that's intentional, this is an audit trail, not a
    single flag.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    session_id = models.CharField(max_length=255, blank=True)
    visit_recording = models.ForeignKey(
        VisitRecording, on_delete=models.CASCADE, related_name="consents"
    )

    consented_at = models.DateTimeField(auto_now_add=True)
    consent_text_version = models.CharField(
        max_length=20, help_text="Which wording of the consent screen was shown."
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-consented_at"]

    def __str__(self):
        return f"Consent for visit {self.visit_recording_id} @ {self.consented_at:%Y-%m-%d %H:%M}"
