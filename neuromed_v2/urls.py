from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from .views import HomeView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", HomeView.as_view(), name="home"),
    path("privacy/", TemplateView.as_view(template_name="legal/privacy.html"), name="legal_privacy"),
    path("terms/", TemplateView.as_view(template_name="legal/terms.html"), name="legal_terms"),
    path("", include("chat.urls")),
    path("visits/", include("visits.urls")),
    path("documents/", include("documents.urls")),
    path("care-circle/", include("care_circle.urls")),
    path("accounts/", include("accounts.urls")),
]
