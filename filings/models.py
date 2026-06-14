from __future__ import annotations

from django.db import models
from django.urls import reverse


ITEM_TITLES = {
    "1": "Business",
    "1A": "Risk Factors",
    "1B": "Unresolved Staff Comments",
    "1C": "Cybersecurity",
    "2": "Properties",
    "3": "Legal Proceedings",
    "4": "Mine Safety Disclosures",
    "5": "Market for Registrant's Common Equity",
    "6": "Reserved",
    "7": "Management's Discussion and Analysis",
    "7A": "Quantitative and Qualitative Disclosures About Market Risk",
    "8": "Financial Statements and Supplementary Data",
    "9": "Changes in and Disagreements With Accountants",
    "9A": "Controls and Procedures",
    "9B": "Other Information",
    "9C": "Disclosure Regarding Foreign Jurisdictions",
    "10": "Directors, Executive Officers and Corporate Governance",
    "11": "Executive Compensation",
    "12": "Security Ownership",
    "13": "Certain Relationships and Related Transactions",
    "14": "Principal Accountant Fees and Services",
    "15": "Exhibits and Financial Statement Schedules",
}

DEFAULT_SELECTED_ITEMS = ("1", "1A", "7")
ITEM_CHOICES = tuple((code, f"Item {code}. {title}") for code, title in ITEM_TITLES.items())


class Company(models.Model):
    cik = models.PositiveBigIntegerField(unique=True)
    name = models.CharField(max_length=255)
    ticker = models.CharField(max_length=32, blank=True)
    exchange = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ticker", "name"]
        verbose_name_plural = "companies"

    def __str__(self) -> str:
        label = self.ticker or self.name
        return f"{label} ({self.padded_cik})"

    @property
    def padded_cik(self) -> str:
        return str(self.cik).zfill(10)


class Filing(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        DOWNLOADED = "downloaded", "Downloaded"
        EXTRACTED = "extracted", "Extracted"
        FAILED = "failed", "Failed"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="filings")
    accession_number = models.CharField(max_length=32, unique=True)
    form_type = models.CharField(max_length=16)
    filing_date = models.DateField()
    report_date = models.DateField(null=True, blank=True)
    fiscal_year = models.PositiveIntegerField(null=True, blank=True)
    sec_filing_url = models.URLField(max_length=500)
    sec_primary_doc_url = models.URLField(max_length=500)
    raw_text_path = models.CharField(max_length=500, blank=True)
    primary_document_path = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-filing_date", "company__ticker"]

    def __str__(self) -> str:
        return f"{self.company.ticker or self.company.name} {self.form_type} {self.filing_date}"

    def get_absolute_url(self) -> str:
        return reverse("filings:detail", args=[self.pk])


class FilingItem(models.Model):
    TARGET_ITEMS = ("1", "1A", "1B", "1C", "2", "3", "4")

    filing = models.ForeignKey(Filing, on_delete=models.CASCADE, related_name="items")
    item_code = models.CharField(max_length=3)
    title = models.CharField(max_length=255)
    extracted_text = models.TextField()
    start_offset = models.PositiveIntegerField(null=True, blank=True)
    end_offset = models.PositiveIntegerField(null=True, blank=True)
    confidence = models.FloatField(default=0.0)
    warnings = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["filing", "item_code"]
        constraints = [
            models.UniqueConstraint(fields=["filing", "item_code"], name="unique_filing_item_code"),
        ]

    @property
    def sort_order(self) -> int:
        try:
            return list(ITEM_TITLES).index(self.item_code)
        except ValueError:
            return len(ITEM_TITLES)

    def __str__(self) -> str:
        return f"{self.filing}: Item {self.item_code}"


class FilingChunk(models.Model):
    filing = models.ForeignKey(Filing, on_delete=models.CASCADE, related_name="chunks")
    item = models.ForeignKey(FilingItem, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.PositiveIntegerField()
    item_code = models.CharField(max_length=3)
    text = models.TextField()
    start_offset = models.PositiveIntegerField()
    end_offset = models.PositiveIntegerField()
    embedding = models.JSONField(null=True, blank=True)
    embedding_model = models.CharField(max_length=255, blank=True)
    embedding_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["filing", "item_code", "chunk_index"]
        constraints = [
            models.UniqueConstraint(fields=["filing", "item_code", "chunk_index"], name="unique_filing_chunk"),
        ]

    def __str__(self) -> str:
        return f"{self.filing} Item {self.item_code} chunk {self.chunk_index}"
