from django.contrib import admin

from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("filing", "role", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("message", "filing__company__ticker")
