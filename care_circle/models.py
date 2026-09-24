"""
Care-circle sharing — new in v2, no v1 equivalent. See ARCHITECTURE.md
§ Care circle and the storyboard scenes 06-07 ("The Aira Visit").

One visit, many viewers, each in their own language, delivered on their
own schedule. This is the diaspora/caregiver wedge from the roadmap.
"""
from django.conf import settings
from django.db import models


class CareCircle(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="care_circles"
    )
    visit_recording = models.ForeignKey(
        "visits.VisitRecording", null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Care circle for {self.owner} (visit {self.visit_recording_id})"


class CareCircleMember(models.Model):
    class DeliveryMode(models.TextChoices):
        ASYNC_DIGEST = "async_digest", "Async digest"
        LIVE = "live", "Live access"

    circle = models.ForeignKey(CareCircle, on_delete=models.CASCADE, related_name="members")
    invited_email = models.EmailField()
    preferred_language = models.CharField(max_length=10, default="en")
    delivery_mode = models.CharField(
        max_length=20, choices=DeliveryMode.choices, default=DeliveryMode.ASYNC_DIGEST
    )
    invited_at = models.DateTimeField(auto_now_add=True)
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("circle", "invited_email")]

    def __str__(self):
        return f"{self.invited_email} ({self.preferred_language}) on circle {self.circle_id}"
