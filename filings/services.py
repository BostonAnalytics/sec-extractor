from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.db import transaction

from .embedding import create_chunks_for_filing, embed_filing_chunks
from .extraction import normalize_item_codes, persist_extracted_items, submission_primary_html
from .models import Company, Filing
from .sec_client import FilingCandidate, SecClient


@dataclass
class IngestionResult:
    filing: Filing
    created: bool
    extracted_item_count: int
    embedded_chunk_count: int
    embedding_error: str = ""


def upsert_company(cik: int, name: str, ticker: str = "", exchange: str = "") -> Company:
    company, _ = Company.objects.update_or_create(
        cik=cik,
        defaults={"name": name, "ticker": ticker, "exchange": exchange},
    )
    return company


def storage_dir_for(filing: Filing) -> Path:
    return Path(settings.SEC_STORAGE_ROOT) / str(filing.company.cik) / filing.accession_number.replace("-", "")


@transaction.atomic
def create_or_update_filing(company: Company, candidate: FilingCandidate) -> tuple[Filing, bool]:
    filing, created = Filing.objects.update_or_create(
        accession_number=candidate.accession_number,
        defaults={
            "company": company,
            "form_type": candidate.form_type,
            "filing_date": candidate.filing_date,
            "report_date": candidate.report_date,
            "fiscal_year": candidate.fiscal_year,
            "sec_filing_url": candidate.sec_filing_url,
            "sec_primary_doc_url": candidate.sec_primary_doc_url,
        },
    )
    return filing, created


def download_and_extract(
    filing: Filing,
    client: SecClient | None = None,
    item_codes: Iterable[str] | None = None,
) -> IngestionResult:
    selected_codes = normalize_item_codes(item_codes)
    client = client or SecClient()
    target_dir = storage_dir_for(filing)
    target_dir.mkdir(parents=True, exist_ok=True)
    raw_path = target_dir / f"{filing.accession_number}.txt"
    primary_path = target_dir / "primary-document.html"

    try:
        raw_submission = raw_path.read_text(encoding="utf-8", errors="ignore") if raw_path.exists() else client.get_text(filing.sec_filing_url)
        raw_path.write_text(raw_submission, encoding="utf-8")

        if primary_path.exists():
            primary_html = primary_path.read_text(encoding="utf-8", errors="ignore")
        else:
            try:
                primary_html = client.get_text(filing.sec_primary_doc_url)
            except Exception:
                primary_html = submission_primary_html(raw_submission)
            primary_path.write_text(primary_html, encoding="utf-8")

        filing.raw_text_path = str(raw_path.relative_to(settings.BASE_DIR))
        filing.primary_document_path = str(primary_path.relative_to(settings.BASE_DIR))
        filing.status = Filing.Status.DOWNLOADED
        filing.error_message = ""
        filing.save()

        saved_items = persist_extracted_items(filing, primary_html, item_codes=selected_codes)
        create_chunks_for_filing(filing)

        embedded_count, embedding_error = embed_filing_chunks(filing)

        filing.status = Filing.Status.EXTRACTED
        filing.error_message = embedding_error
        filing.save(update_fields=["status", "error_message", "updated_at"])
        return IngestionResult(filing, False, len(saved_items), embedded_count, embedding_error)
    except Exception as exc:
        filing.status = Filing.Status.FAILED
        filing.error_message = str(exc)
        filing.save(update_fields=["status", "error_message", "updated_at"])
        raise


def ingest_candidate(
    company: Company,
    candidate: FilingCandidate,
    client: SecClient | None = None,
    item_codes: Iterable[str] | None = None,
) -> IngestionResult:
    filing, created = create_or_update_filing(company, candidate)
    result = download_and_extract(filing, client=client, item_codes=item_codes)
    result.created = created
    return result
