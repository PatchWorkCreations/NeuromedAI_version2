from django.contrib import admin

from .models import EscalationEvent


@admin.register(EscalationEvent)
class EscalationEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "category", "user", "session_id")
    list_filter = ("category", "created_at")
    readonly_fields = [f.name for f in EscalationEvent._meta.fields]

    def has_add_permission(self, request):
        return False  # events are only ever created by safety.engine, never by hand
