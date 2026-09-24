from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("chat/", views.chat_page, name="room"),
    path("chat/<int:conversation_id>/", views.conversation_page, name="conversation"),
    path("chat/<int:conversation_id>/delete/", views.delete_conversation, name="delete_conversation"),
    path("api/send-chat/", views.send_chat, name="send_chat"),
]
