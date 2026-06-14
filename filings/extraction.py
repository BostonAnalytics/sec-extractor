from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from typing import Iterable

from bs4 import BeautifulSoup

from .models import DEFAULT_SELECTED_ITEMS, ITEM_TITLES, FilingItem


TARGET_ITEMS = ("1", "1A", "1B", "1C", "2", "3", "4")
NEXT_BOUNDARY_ITEMS = tuple(ITEM_TITLES)


@dataclass
class ExtractedItem:
    item_code: str
    title: str
    text: str
    start_offset: int | None = None
    end_offset: int | None = None
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)


def normalize_item_codes(item_codes: Iterable[str] | None = None) -> tuple[str, ...]:
    codes = tuple(dict.fromkeys(str(code).upper().strip() for code in (item_codes or TARGET_ITEMS)))
    invalid = [code for code in codes if code not in ITEM_TITLES]
    if invalid:
        raise ValueError(f"Unsupported SEC item code(s): {', '.join(invalid)}")
    return codes


def clean_sec_item_text(raw_text: str) -> str:
    text = unescape(str(raw_text))
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"Table of Contents", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bITEM\s+\d+[A-Z]?\.?\s*$", " ", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = unescape(text)
    text = re.sub(r"\xa0", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def submission_primary_html(raw_submission: str) -> str:
    documents = re.findall(
        r"<DOCUMENT>(.*?)</DOCUMENT>",
        raw_submission,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for document in documents:
        type_match = re.search(r"<TYPE>\s*([^\n\r<]+)", document, flags=re.IGNORECASE)
        text_match = re.search(r"<TEXT>(.*?)</TEXT>", document, flags=re.IGNORECASE | re.DOTALL)
        if not type_match or not text_match:
            continue
        doc_type = type_match.group(1).strip().upper()
        if doc_type in {"10-K", "10-K405", "10KSB"}:
            return text_match.group(1).strip()
    return raw_submission


def _heading_pattern(item_code: str) -> re.Pattern:
    code = re.escape(item_code)
    title = re.escape(ITEM_TITLES.get(item_code, ""))
    title = title.replace(r"\ ", r"\s+")
    return re.compile(
        rf"(?is)(?:^|\n|\r|>)\s*item\s+{code}\.?\s*(?:{title})?",
        flags=re.IGNORECASE,
    )


def _find_headings(text: str, item_code: str) -> list[re.Match]:
    pattern = _heading_pattern(item_code)
    matches = list(pattern.finditer(text))
    if len(matches) <= 1:
        return matches

    part_i = re.search(r"\bPART\s+I\b", text, flags=re.IGNORECASE)
    if part_i:
        after_part_i = [match for match in matches if match.start() > part_i.start()]
        if after_part_i:
            return after_part_i

    # The first repeated heading is often the table of contents. Prefer later hits.
    threshold = min(len(text), 5000)
    later = [match for match in matches if match.start() > threshold]
    return later or matches


def extract_items_from_html(html: str, item_codes: Iterable[str] | None = None) -> list[ExtractedItem]:
    return extract_items_from_text(html_to_text(html), item_codes=item_codes)


def extract_items_from_text(text: str, item_codes: Iterable[str] | None = None) -> list[ExtractedItem]:
    selected_codes = normalize_item_codes(item_codes)
    heading_by_code = {code: _find_headings(text, code) for code in NEXT_BOUNDARY_ITEMS}
    extracted: list[ExtractedItem] = []
    previous_start = -1

    for item_code in selected_codes:
        candidates = heading_by_code.get(item_code, [])
        viable = [match for match in candidates if match.start() > previous_start]
        chosen = viable[0] if viable else (candidates[0] if candidates else None)
        title = ITEM_TITLES[item_code]

        if not chosen:
            extracted.append(
                ExtractedItem(
                    item_code=item_code,
                    title=title,
                    text="",
                    warnings=[f"Item {item_code} heading was not found."],
                )
            )
            continue

        next_offsets = []
        selected_index = list(NEXT_BOUNDARY_ITEMS).index(item_code)
        for boundary_code in NEXT_BOUNDARY_ITEMS[selected_index + 1 :]:
            next_offsets.extend(match.start() for match in heading_by_code.get(boundary_code, []) if match.start() > chosen.start())

        end = min(next_offsets) if next_offsets else len(text)
        item_text = clean_sec_item_text(text[chosen.end() : end])
        warning = [] if item_text else [f"Item {item_code} was found but no extractable text followed the heading."]
        confidence = 0.95 if item_text else 0.25
        previous_start = chosen.start()

        extracted.append(
            ExtractedItem(
                item_code=item_code,
                title=title,
                text=item_text,
                start_offset=chosen.start(),
                end_offset=end,
                confidence=confidence,
                warnings=warning,
            )
        )

    return extracted


def persist_extracted_items(
    filing,
    html: str,
    item_codes: Iterable[str] | None = None,
) -> list[FilingItem]:
    selected_codes = normalize_item_codes(item_codes)
    items = extract_items_from_html(html, item_codes=selected_codes)
    saved_items: list[FilingItem] = []

    FilingItem.objects.filter(filing=filing).exclude(item_code__in=selected_codes).delete()

    for item in items:
        saved_item, _ = FilingItem.objects.update_or_create(
            filing=filing,
            item_code=item.item_code,
            defaults={
                "title": item.title,
                "extracted_text": item.text,
                "start_offset": item.start_offset,
                "end_offset": item.end_offset,
                "confidence": item.confidence,
                "warnings": "\n".join(item.warnings),
            },
        )
        saved_items.append(saved_item)

    return saved_items
