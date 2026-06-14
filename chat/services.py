from __future__ import annotations

import re

from django.conf import settings

from filings.embedding import cosine_similarity, get_embedding_client
from filings.models import Filing, FilingChunk, FilingItem

from .reranking import rerank_snippets
from .services_types import Snippet


def _extractive_snippet(text: str, query: str, width: int = 600) -> str:
    terms = re.findall(r"[a-z0-9]{3,}", query.lower())
    lower_text = text.lower()
    positions = [lower_text.find(term) for term in terms if lower_text.find(term) >= 0]
    if not positions:
        return text[:width].strip()
    start = max(0, min(positions) - width // 4)
    end = min(len(text), start + width)
    return text[start:end].strip()


def search_filing_chunks(filing: Filing, query: str, limit: int | None = None) -> list[Snippet]:
    limit = limit or settings.RAG_TOP_K
    chunks = list(
        FilingChunk.objects.filter(filing=filing)
        .exclude(embedding__isnull=True)
        .select_related("item")
        .order_by("id")
    )
    if not chunks:
        return []

    try:
        query_embedding = get_embedding_client().embed_query(query)
    except Exception:
        return []

    ranked: list[tuple[float, FilingChunk]] = [
        (cosine_similarity(chunk.embedding or [], query_embedding), chunk) for chunk in chunks
    ]
    ranked.sort(key=lambda row: row[0], reverse=True)
    snippets = [
        Snippet(
            item_code=chunk.item_code,
            title=chunk.item.title,
            text=chunk.text,
            score=float(score),
        )
        for score, chunk in ranked[: settings.RAG_CANDIDATE_K]
    ]
    return rerank_snippets(query, snippets, limit)


def search_filing_items(filing: Filing, query: str, limit: int | None = None) -> list[Snippet]:
    limit = limit or settings.RAG_TOP_K
    vector_snippets = search_filing_chunks(filing, query, limit)
    if vector_snippets:
        return vector_snippets

    terms = re.findall(r"[a-z0-9]{3,}", query.lower())
    snippets: list[Snippet] = []
    for item in FilingItem.objects.filter(filing=filing).exclude(extracted_text=""):
        text = item.extracted_text
        lower_text = text.lower()
        score = float(sum(lower_text.count(term) for term in terms))
        if score <= 0 and terms:
            continue
        snippets.append(
            Snippet(
                item_code=item.item_code,
                title=item.title,
                text=_extractive_snippet(text, query),
                score=score,
            )
        )

    return sorted(snippets, key=lambda snippet: snippet.score, reverse=True)[:limit]


def answer_question(filing: Filing, question: str) -> tuple[str, list[dict]]:
    snippets = search_filing_items(filing, question)
    if not snippets:
        return "I do not have enough extracted filing evidence to answer this question.", []

    citations = [
        {
            "item_code": snippet.item_code,
            "title": snippet.title,
            "snippet": snippet.text,
            "score": snippet.score,
        }
        for snippet in snippets
    ]
    cited_items = ", ".join(f"Item {snippet.item_code}" for snippet in snippets)
    answer = (
        "Based on the selected extracted filing text, the strongest evidence appears in "
        f"{cited_items}. Review the cited excerpts below for the exact filing language."
    )
    return answer, citations
