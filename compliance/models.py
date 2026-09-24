"""
Compliance as a product surface — see Keep, Rework, Cut § Build new.
Not a substitute for the actual breach-notice policy and privacy policy
documents (those are legal artifacts, drafted with counsel) — this is
just where their version history and any logged incident lives so the
FTC Health Breach Notification Rule timeline (60 days to notify) has a
real system of record behind it instead of someone's memory.
"""
from django.db import models


class PolicyVersion(models.Model):
    class Kind(models.TextChoices):
        PRIVACY_POLICY = "privacy_policy", "Privacy policy"
        BREACH_NOTICE_PLAN = "breach_notice_plan", "Breach notice plan"

    kind = models.CharField(max_length=32, choices=Kind.choices)
    version_label = models.CharField(max_length=20)
    published_at = models.DateTimeField(auto_now_add=True)
    document_url = models.URLField(blank=True)


class BreachIncident(models.Model):
    """Hopefully never populated — exists so the 60-day notification clock has a start date on record."""
    discovered_at = models.DateTimeField()
    affected_user_count = models.PositiveIntegerField(default=0)
    description = models.TextField()
    ftc_notified_at = models.DateTimeField(null=True, blank=True)
    users_notified_at = models.DateTimeField(null=True, blank=True)
