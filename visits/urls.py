from django.urls import path

from . import views

app_name = "visits"

urlpatterns = [
    path("", views.visit_list, name="list"),
    path("record/", views.record_page, name="record"),
    path("consent/", views.consent_text, name="consent_text"),
    path("start/", views.start_visit, name="start_visit"),
    path("transcribe/", views.voice_transcribe, name="voice_transcribe"),
    path("<int:visit_id>/", views.visit_detail, name="detail"),
    path("<int:visit_id>/summarize/", views.summarize_visit, name="summarize_visit"),
    path("<int:visit_id>/discard/", views.discard_visit, name="discard"),
]
