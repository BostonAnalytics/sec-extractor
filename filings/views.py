from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import FilingSearchForm
from .models import Filing, ITEM_TITLES
from .sec_client import CompanyCandidate, FilingCandidate, SecClient
from .services import create_or_update_filing, download_and_extract, upsert_company


def _selected_item_labels(item_codes: list[str] | tuple[str, ...]) -> list[str]:
    return [f"Item {code}. {ITEM_TITLES.get(code, '')}" for code in item_codes]


def _company_from_session(row: dict) -> CompanyCandidate:
    return CompanyCandidate(
        cik=int(row["cik"]),
        name=row["name"],
        ticker=row.get("ticker", ""),
        exchange=row.get("exchange", ""),
        score=float(row.get("score", 0)),
    )


def _filing_from_session(row: dict) -> FilingCandidate:
    from datetime import date

    filing_date = date.fromisoformat(row["filing_date"])
    report_date = date.fromisoformat(row["report_date"]) if row.get("report_date") else None
    return FilingCandidate(
        accession_number=row["accession_number"],
        form_type=row["form_type"],
        filing_date=filing_date,
        report_date=report_date,
        primary_document=row.get("primary_document", ""),
        sec_filing_url=row["sec_filing_url"],
        sec_primary_doc_url=row["sec_primary_doc_url"],
    )


def _filing_to_session(candidate: FilingCandidate) -> dict:
    return {
        "accession_number": candidate.accession_number,
        "form_type": candidate.form_type,
        "filing_date": candidate.filing_date.isoformat(),
        "report_date": candidate.report_date.isoformat() if candidate.report_date else "",
        "primary_document": candidate.primary_document,
        "sec_filing_url": candidate.sec_filing_url,
        "sec_primary_doc_url": candidate.sec_primary_doc_url,
    }


def home(request):
    form = FilingSearchForm(request.GET or None)
    if request.GET and form.is_valid():
        client = SecClient()
        candidates = client.lookup_companies(form.cleaned_data["company"])
        if not candidates:
            messages.error(request, "No matching SEC companies were found.")
        else:
            request.session["filing_search"] = {
                "company": form.cleaned_data["company"],
                "year": form.cleaned_data["year"],
                "year_mode": form.cleaned_data["year_mode"],
                "item_codes": form.cleaned_data["item_codes"],
            }
            request.session["company_candidates"] = [candidate.__dict__ for candidate in candidates]
            return redirect("filings:confirm_company")

    recent_filings = Filing.objects.select_related("company").prefetch_related("items")[:10]
    return render(request, "filings/home.html", {"form": form, "recent_filings": recent_filings})


@require_http_methods(["GET", "POST"])
def confirm_company(request):
    search = request.session.get("filing_search")
    candidate_rows = request.session.get("company_candidates", [])
    if not search or not candidate_rows:
        return redirect("filings:home")

    candidates = [_company_from_session(row) for row in candidate_rows]
    if request.method == "POST":
        selected_index = int(request.POST["candidate_index"])
        request.session["selected_company"] = candidates[selected_index].__dict__
        return redirect("filings:select_filing")

    return render(
        request,
        "filings/confirm_company.html",
        {
            "search": search,
            "candidates": list(enumerate(candidates)),
            "selected_item_labels": _selected_item_labels(search["item_codes"]),
        },
    )


@require_http_methods(["GET", "POST"])
def select_filing(request):
    search = request.session.get("filing_search")
    selected_company = request.session.get("selected_company")
    if not search or not selected_company:
        return redirect("filings:home")

    client = SecClient()
    company_candidate = _company_from_session(selected_company)

    if request.method == "POST":
        candidate = _filing_from_session(request.session["filing_candidates"][int(request.POST["candidate_index"])])
        company = upsert_company(
            company_candidate.cik,
            company_candidate.name,
            company_candidate.ticker,
            company_candidate.exchange,
        )
        filing, _ = create_or_update_filing(company, candidate)
        try:
            download_and_extract(filing, client=client, item_codes=search["item_codes"])
            messages.success(request, "Filing downloaded and selected SEC items extracted.")
        except Exception as exc:
            messages.error(request, f"Download failed: {exc}")
        return redirect(filing.get_absolute_url())

    candidates = client.filing_candidates(company_candidate.cik, search["year"], search["year_mode"])
    request.session["filing_candidates"] = [_filing_to_session(candidate) for candidate in candidates]
    return render(
        request,
        "filings/select_filing.html",
        {
            "search": search,
            "company": company_candidate,
            "candidates": list(enumerate(candidates)),
            "selected_item_labels": _selected_item_labels(search["item_codes"]),
        },
    )


def detail(request, pk: int):
    filing = get_object_or_404(
        Filing.objects.select_related("company").prefetch_related("items", "chunks"),
        pk=pk,
    )
    return render(request, "filings/detail.html", {"filing": filing})
