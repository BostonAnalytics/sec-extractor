from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from filings.models import Filing

from .forms import ChatForm
from .models import ChatMessage
from .services import answer_question


@require_http_methods(["GET", "POST"])
def filing_chat(request, filing_id: int):
    filing = get_object_or_404(Filing.objects.select_related("company"), pk=filing_id)
    form = ChatForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        question = form.cleaned_data["question"]
        ChatMessage.objects.create(filing=filing, role=ChatMessage.Role.USER, message=question)
        answer, citations = answer_question(filing, question)
        ChatMessage.objects.create(
            filing=filing,
            role=ChatMessage.Role.ASSISTANT,
            message=answer,
            citations=citations,
        )
        return redirect("chat:filing_chat", filing_id=filing.pk)

    messages = filing.chat_messages.all()
    return render(request, "chat/filing_chat.html", {"filing": filing, "form": form, "messages": messages})
