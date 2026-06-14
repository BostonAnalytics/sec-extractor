from __future__ import annotations

from dataclasses import replace

import requests
from django.conf import settings

from .services_types import Snippet


class CohereReranker:
    def __init__(self) -> None:
        self.api_key = settings.COHERE_KEY
        self.model = settings.COHERE_RERANK_MODEL

    def rerank(self, query: str, snippets: list[Snippet], limit: int) -> list[Snippet]:
        response = requests.post(
            "https://api.cohere.com/v2/rerank",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "query": query,
                "documents": [snippet.text for snippet in snippets],
                "top_n": limit,
            },
            timeout=30,
        )
        response.raise_for_status()
        ranked: list[Snippet] = []
        for result in response.json().get("results", []):
            snippet = snippets[result["index"]]
            ranked.append(replace(snippet, score=float(result.get("relevance_score", snippet.score))))
        return ranked


def rerank_snippets(query: str, snippets: list[Snippet], limit: int) -> list[Snippet]:
    if not settings.COHERE_RERANK_ENABLED or not settings.COHERE_KEY:
        return snippets[:limit]
    try:
        return CohereReranker().rerank(query, snippets, limit)
    except Exception:
        return snippets[:limit]
