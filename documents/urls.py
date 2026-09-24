from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("", views.document_list, name="list"),
    path("<int:document_id>/", views.document_detail, name="detail"),
    path("<int:document_id>/delete/", views.document_delete, name="delete"),
    path("<int:document_id>/file/", views.document_file, name="file"),
]
