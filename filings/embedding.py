from __future__ import annotations

import math
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

import requests
from django.conf import settings

from .models import Filing, FilingChunk


class EmbeddingConfigurationError(RuntimeError):
    pass


class EmbeddingRequestError(RuntimeError):
    pass


class EmbeddingClient(Protocol):
    model: str
    deployment: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


@dataclass
class TextChunk:
    text: str
    start_offset: int
    end_offset: int


def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[TextChunk]:
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    clean_text = " ".join(str(text).split())
    chunks: list[TextChunk] = []
    start = 0
    while start < len(clean_text):
        end = min(len(clean_text), start + chunk_size)
        if end < len(clean_text):
            boundary = clean_text.rfind(" ", start, end)
            if boundary > start + int(chunk_size * 0.6):
                end = boundary
        chunk = clean_text[start:end].strip()
        if chunk:
            chunks.append(TextChunk(chunk, start, end))
        start = max(end - chunk_overlap, end if end == len(clean_text) else start + 1)
        if end == len(clean_text):
            break
    return chunks


def create_chunks_for_filing(filing: Filing) -> list[FilingChunk]:
    FilingChunk.objects.filter(filing=filing).delete()
    created_chunks: list[FilingChunk] = []

    for item in filing.items.exclude(extracted_text="").order_by("item_code"):
        for index, chunk in enumerate(
            chunk_text(
                item.extracted_text,
                settings.RAG_CHUNK_SIZE,
                settings.RAG_CHUNK_OVERLAP,
            )
        ):
            created_chunks.append(
                FilingChunk.objects.create(
                    filing=filing,
                    item=item,
                    chunk_index=index,
                    item_code=item.item_code,
                    text=chunk.text,
                    start_offset=chunk.start_offset,
                    end_offset=chunk.end_offset,
                )
            )

    return created_chunks


class AzureEmbeddingClient:
    def __init__(self) -> None:
        if not settings.AZURE_API_KEY or not settings.AZURE_ENDPOINT:
            raise EmbeddingConfigurationError("Azure embedding settings are incomplete.")
        self.model = settings.AZURE_EMBEDDING_MODEL
        self.deployment = settings.AZURE_EMBEDDING_DEPLOYMENT or self.model
        self.endpoint = settings.AZURE_ENDPOINT.rstrip("/")
        self.session = requests.Session()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed_batches(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([settings.RAG_QUERY_INSTRUCTION + text])[0]

    def _embed_batches(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        batch_size = settings.RAG_EMBEDDING_BATCH_SIZE
        for start in range(0, len(texts), batch_size):
            embeddings.extend(self._embed_with_retries(texts[start : start + batch_size]))
        return embeddings

    def _embed_with_retries(self, texts: list[str]) -> list[list[float]]:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return self._send_batch(texts)
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(1 + attempt)
        raise EmbeddingRequestError(str(last_error))

    def _send_batch(self, texts: list[str]) -> list[list[float]]:
        url = (
            f"{self.endpoint}/openai/deployments/{self.deployment}/embeddings"
            f"?api-version={settings.AZURE_OPENAI_API_VERSION}"
        )
        response = self.session.post(
            url,
            headers={"api-key": settings.AZURE_API_KEY},
            json={"input": texts, "model": self.model},
            timeout=60,
        )
        response.raise_for_status()
        return self._parse_embeddings(response.json())

    @staticmethod
    def _parse_embeddings(payload: dict) -> list[list[float]]:
        return [row["embedding"] for row in sorted(payload["data"], key=lambda item: item.get("index", 0))]


class HuggingFaceEmbeddingClient:
    deployment = "huggingface-inference"

    def __init__(self) -> None:
        if not settings.HUGGINGFACE_API_KEY:
            raise EmbeddingConfigurationError("Hugging Face embedding settings are incomplete.")
        self.model = settings.HUGGINGFACE_EMBEDDING_MODEL
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"})

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed_batches(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([settings.RAG_QUERY_INSTRUCTION + text])[0]

    def _embed_batches(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            embeddings.append(self._embed_with_retries(text))
        return embeddings

    def _embed_with_retries(self, text: str) -> list[float]:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return self._send_batch(text)
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(1 + attempt)
        raise EmbeddingRequestError(str(last_error))

    def _send_batch(self, text: str) -> list[float]:
        response = self.session.post(settings.HUGGINGFACE_BASE_URL, json={"inputs": text}, timeout=60)
        response.raise_for_status()
        return self._parse_embeddings(response.json())

    @classmethod
    def _parse_embeddings(cls, payload):
        if cls._is_number_list(payload):
            return [float(value) for value in payload]
        if isinstance(payload, list) and payload and cls._is_number_list(payload[0]):
            return cls._mean_pool(payload)
        if isinstance(payload, list) and payload and isinstance(payload[0], list):
            if payload[0] and isinstance(payload[0][0], list):
                return [cls._mean_pool(document) for document in payload]
            return cls._mean_pool(payload)
        raise EmbeddingRequestError("Unexpected Hugging Face embedding payload.")

    @staticmethod
    def _is_number_list(value) -> bool:
        return isinstance(value, list) and all(isinstance(item, int | float) for item in value)

    @staticmethod
    def _mean_pool(rows: list[list[float]]) -> list[float]:
        if not rows:
            return []
        width = len(rows[0])
        return [sum(row[index] for row in rows) / len(rows) for index in range(width)]


def get_embedding_client() -> EmbeddingClient:
    provider = settings.RAG_EMBEDDING_PROVIDER.lower()
    if provider == "azure":
        return AzureEmbeddingClient()
    if provider == "huggingface":
        return HuggingFaceEmbeddingClient()
    if settings.AZURE_API_KEY and settings.AZURE_ENDPOINT:
        return AzureEmbeddingClient()
    if settings.HUGGINGFACE_API_KEY:
        return HuggingFaceEmbeddingClient()
    raise EmbeddingConfigurationError("No embedding provider is configured.")


def embed_filing_chunks(filing: Filing, client: EmbeddingClient | None = None) -> tuple[int, str]:
    chunks = list(FilingChunk.objects.filter(filing=filing).order_by("id"))
    if not chunks:
        return 0, ""

    try:
        client = client or get_embedding_client()
        texts = [chunk.text for chunk in chunks]
        embeddings = client.embed_documents(texts)
    except Exception as exc:
        FilingChunk.objects.filter(id__in=[chunk.id for chunk in chunks]).update(embedding_error=str(exc))
        return 0, str(exc)

    for chunk, embedding in zip(chunks, embeddings, strict=False):
        chunk.embedding = embedding
        chunk.embedding_model = getattr(client, "model", "")
        chunk.embedding_error = ""
        chunk.save(update_fields=["embedding", "embedding_model", "embedding_error", "updated_at"])

    return len(embeddings), ""


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    left = list(left)
    right = list(right)
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def build_chunks_and_embeddings(filing: Filing) -> tuple[int, str]:
    create_chunks_for_filing(filing)
    return embed_filing_chunks(filing)
