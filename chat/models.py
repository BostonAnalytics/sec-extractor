from django.db import models

from filings.models import Filing


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    filing = models.ForeignKey(Filing, on_delete=models.CASCADE, related_name="chat_messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    message = models.TextField()
    citations = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.role}: {self.message[:80]}"
