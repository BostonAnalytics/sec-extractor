from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",") if host.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "filings",
    "chat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "sec_extractor.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "sec_extractor.wsgi.application"


def database_from_url(database_url: str | None = None) -> dict:
    database_url = database_url or os.getenv("DATABASE_URL")
    if not database_url:
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}

    parsed = urlparse(database_url)
    if parsed.scheme.startswith("postgres"):
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
        }

    raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme}")


DATABASES = {"default": database_from_url()}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "SecExtractor contact@example.com")
SEC_STORAGE_ROOT = Path(os.getenv("SEC_STORAGE_ROOT", BASE_DIR / "var" / "sec_filings"))
SEC_REQUESTS_PER_SECOND = float(os.getenv("SEC_REQUESTS_PER_SECOND", "6"))

RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "500"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "50"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_CANDIDATE_K = int(os.getenv("RAG_CANDIDATE_K", "12"))
RAG_EMBEDDING_BATCH_SIZE = int(os.getenv("RAG_EMBEDDING_BATCH_SIZE", "30"))
RAG_EMBEDDING_PROVIDER = os.getenv("RAG_EMBEDDING_PROVIDER", "auto")
RAG_QUERY_INSTRUCTION = os.getenv(
    "RAG_QUERY_INSTRUCTION",
    "Represent this question for searching relevant passages: ",
)

AZURE_API_KEY = os.getenv("AZURE_API_KEY", os.getenv("AZURE_OPENAI_API_KEY", ""))
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT", os.getenv("AZURE_OPENAI_ENDPOINT", ""))
AZURE_FOUNDRY_API_VERSION = os.getenv("AZURE_FOUNDRY_API_VERSION", "2024-05-01-preview")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
AZURE_EMBEDDING_MODEL = os.getenv("AZURE_EMBEDDING_MODEL", "text-embedding-3-small")
AZURE_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "")

HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", os.getenv("HF_KEY", ""))
HUGGINGFACE_BASE_URL = os.getenv(
    "HUGGINGFACE_BASE_URL",
    "https://api-inference.huggingface.co/pipeline/feature-extraction/BAAI/bge-base-en-v1.5",
)
HUGGINGFACE_EMBEDDING_MODEL = os.getenv("HUGGINGFACE_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")

COHERE_KEY = os.getenv("COHERE_KEY", os.getenv("COHERE_API_KEY", ""))
COHERE_RERANK_MODEL = os.getenv("COHERE_RERANK_MODEL", "rerank-english-v3.0")
COHERE_RERANK_ENABLED = os.getenv("COHERE_RERANK_ENABLED", "false").lower() == "true"

LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_KEY", os.getenv("LANGCHAIN_API_KEY", ""))
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false")
LANGCHAIN_ENDPOINT = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "sec-extractor")

if LANGCHAIN_API_KEY:
    os.environ.setdefault("LANGCHAIN_API_KEY", LANGCHAIN_API_KEY)
