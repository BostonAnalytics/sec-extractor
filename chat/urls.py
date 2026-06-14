from django.urls import path

from . import views


app_name = "chat"

urlpatterns = [
    path("<int:filing_id>/", views.filing_chat, name="filing_chat"),
]
