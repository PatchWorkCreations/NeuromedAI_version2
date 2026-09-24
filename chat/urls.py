from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("chat/", views.chat_page, name="room"),
    path("api/send-chat/", views.send_chat, name="send_chat"),
]
