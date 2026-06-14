from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import requests
from django.conf import settings
from django.utils.dateparse import parse_date


SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"
SEC_DATA_BASE = "https://data.sec.gov"
SEC_FILES_BASE = "https://www.sec.gov/files"


def normalize_company_name(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    suffixes = r"\b(inc|corp|corporation|co|company|ltd|plc|class a|common stock)\b"
    value = re.sub(suffixes, " ", value)
    return re.sub(r"\s+", " ", value).strip()


@dataclass
class CompanyCandidate:
    cik: int
    name: str
    ticker: str
    exchange: str
    score: float

    @property
    def padded_cik(self) -> str:
        return str(self.cik).zfill(10)


@dataclass
class FilingCandidate:
    accession_number: str
    form_type: str
    filing_date: date
    report_date: date | None
    primary_document: str
    sec_filing_url: str
    sec_primary_doc_url: str

    @property
    def fiscal_year(self) -> int | None:
        return self.report_date.year if self.report_date else None


class SecClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": settings.SEC_USER_AGENT,
                "Accept-Encoding": "gzip, deflate",
            }
        )
        self._last_request_at = 0.0

    def _rate_limit(self) -> None:
        interval = 1.0 / max(float(settings.SEC_REQUESTS_PER_SECOND), 0.1)
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self._last_request_at = time.monotonic()

    def get(self, url: str) -> requests.Response:
        self._rate_limit()
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response

    def get_json(self, url: str) -> Any:
        return self.get(url).json()

    def get_text(self, url: str) -> str:
        return self.get(url).text

    def company_tickers(self) -> list[dict[str, Any]]:
        cache_dir = Path(settings.SEC_STORAGE_ROOT) / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / "company_tickers_exchange.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))["data"]

        payload = self.get_json(f"{SEC_FILES_BASE}/company_tickers_exchange.json")
        cache_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload["data"]

    def lookup_companies(self, query: str, limit: int = 8) -> list[CompanyCandidate]:
        normalized_query = normalize_company_name(query)
        query_upper = query.upper().strip()
        candidates: list[CompanyCandidate] = []

        for cik, name, ticker, exchange in self.company_tickers():
            normalized_name = normalize_company_name(name)
            score = SequenceMatcher(None, normalized_query, normalized_name).ratio()
            if ticker.upper() == query_upper:
                score += 2.0
            elif query_upper in ticker.upper():
                score += 0.8
            if normalized_query and normalized_query in normalized_name:
                score += 0.6
            if score > 0.35:
                candidates.append(CompanyCandidate(cik=int(cik), name=name, ticker=ticker, exchange=exchange, score=score))

        return sorted(candidates, key=lambda item: item.score, reverse=True)[:limit]

    def submissions(self, cik: int) -> dict[str, Any]:
        return self.get_json(f"{SEC_DATA_BASE}/submissions/CIK{str(cik).zfill(10)}.json")

    def filing_candidates(
        self,
        cik: int,
        year: int,
        year_mode: str = "fiscal",
        form_types: tuple[str, ...] = ("10-K",),
    ) -> list[FilingCandidate]:
        recent = self.submissions(cik)["filings"]["recent"]
        rows = zip(
            recent.get("accessionNumber", []),
            recent.get("form", []),
            recent.get("filingDate", []),
            recent.get("reportDate", []),
            recent.get("primaryDocument", []),
        )
        candidates: list[FilingCandidate] = []
        compact_cik = str(int(cik))

        for accession_number, form_type, filing_date_text, report_date_text, primary_document in rows:
            if form_type not in form_types:
                continue
            filing_date = parse_date(filing_date_text)
            report_date = parse_date(report_date_text) if report_date_text else None
            if not filing_date:
                continue

            candidate_year = report_date.year if year_mode == "fiscal" and report_date else filing_date.year
            if candidate_year != year:
                continue

            accession_no_dash = accession_number.replace("-", "")
            base_url = f"{SEC_ARCHIVES_BASE}/{compact_cik}/{accession_no_dash}"
            candidates.append(
                FilingCandidate(
                    accession_number=accession_number,
                    form_type=form_type,
                    filing_date=filing_date,
                    report_date=report_date,
                    primary_document=primary_document,
                    sec_filing_url=f"{base_url}/{accession_number}.txt",
                    sec_primary_doc_url=f"{base_url}/{primary_document}",
                )
            )

        return sorted(candidates, key=lambda item: item.filing_date, reverse=True)
