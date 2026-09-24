"""
The escalation engine's data model.

See CLAUDE.md boundary #2 and ARCHITECTURE.md § Safety layer: this exists
because v1's red-flag handling lived entirely inside prompt phrasing
("mention red flags calmly"), with nothing enforcing it outside whatever
the model chose to write, and no record of when it happened. Every check
below runs as a discrete step and is logged — the log itself is the
published-trust artifact from the roadmap.
"""
from django.conf import settings
from django.db import models


class EscalationCategory(models.TextChoices):
    MEDICATION_STOP_START = "medication_stop_start", "Medication stop/start"
    SEVERE_INTERACTION = "severe_interaction", "Severe drug interaction"
    EMERGENCY_SIGN = "emergency_sign", "Emergency / red-flag symptom"


class EscalationEvent(models.Model):
    """One logged instance of the safety layer intercepting a response."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    session_id = models.CharField(max_length=255, blank=True)  # guest support
    chat_session = models.ForeignKey(
        "chat.ChatSession", null=True, blank=True, on_delete=models.SET_NULL
    )
    visit_recording = models.ForeignKey(
        "visits.VisitRecording", null=True, blank=True, on_delete=models.SET_NULL
    )

    category = models.CharField(max_length=32, choices=EscalationCategory.choices)
    matched_terms = models.JSONField(default=list, blank=True)
    trigger_text = models.TextField(help_text="The user/model text snippet that triggered this event.")
    response_shown = models.TextField(help_text="The exact redirect text shown to the user.")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "created_at"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.get_category_display()} @ {self.created_at:%Y-%m-%d %H:%M}"
