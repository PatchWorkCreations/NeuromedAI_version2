from django.conf import settings
from django.db import models


class ChatSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    session_id = models.CharField(max_length=255, blank=True)
    title = models.CharField(
        max_length=120, blank=True,
        help_text="Set from the first question so the history list reads like a list of topics.",
    )
    tone = models.CharField(max_length=32, default="PlainClinical")
    lang = models.CharField(max_length=10, default="en-US")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    @staticmethod
    def title_from(message: str) -> str:
        text = " ".join((message or "").split())
        if len(text) <= 60:
            return text
        return text[:60].rsplit(" ", 1)[0].rstrip(",.;:") + "…"

    @property
    def display_title(self) -> str:
        if self.title:
            return self.title
        first = self.messages.filter(role="user").order_by("created_at").first()
        return self.title_from(first.content) if first else "New conversation"


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    follow_ups = models.JSONField(
        default=list, blank=True,
        help_text="Aira's suggested next questions (assistant messages only), shown as tappable chips.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
