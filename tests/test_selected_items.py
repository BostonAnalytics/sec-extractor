from datetime import date

from django.test import TestCase

from filings.extraction import extract_items_from_text, persist_extracted_items
from filings.embedding import HuggingFaceEmbeddingClient, create_chunks_for_filing, embed_filing_chunks
from filings.models import Company, Filing


class SelectedItemExtractionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(cik=789019, name="Microsoft Corp", ticker="MSFT", exchange="Nasdaq")
        self.filing = Filing.objects.create(
            company=self.company,
            accession_number="0000000000-26-000001",
            form_type="10-K",
            filing_date=date(2026, 1, 31),
            report_date=date(2025, 12, 31),
            fiscal_year=2025,
            sec_filing_url="https://example.com/raw.txt",
            sec_primary_doc_url="https://example.com/primary.htm",
        )

    def test_extract_items_from_text_honors_selected_codes(self):
        text = """
        Table of Contents
        Item 1. Business
        Business overview text.
        Item 1A. Risk Factors
        Risk factor text.
        Item 7. Management's Discussion and Analysis
        Management discussion text.
        Item 8. Financial Statements and Supplementary Data
        Financial statement text.
        """

        items = extract_items_from_text(text, item_codes=["1A"])

        self.assertEqual([item.item_code for item in items], ["1A"])
        self.assertIn("Risk factor text", items[0].text)
        self.assertNotIn("Business overview text", items[0].text)

    def test_default_extraction_preserves_original_10k_items_and_skips_toc(self):
        text = """
        Table of Contents
        Item 1. Business
        Item 1A. Risk Factors
        Item 1B. Unresolved Staff Comments

        PART I
        Item 1. Business
        We make products and services for customers around the world.

        Item 1A. Risk Factors
        Our business is subject to market, operational, legal, and technology risks.

        Item 1B. Unresolved Staff Comments
        None.

        Item 1C. Cybersecurity
        We maintain cybersecurity risk management processes.

        Item 2. Properties
        We own and lease facilities.

        Item 3. Legal Proceedings
        Legal matters arise in the ordinary course.

        Item 4. Mine Safety Disclosures
        Not applicable.

        Item 5. Market for Registrant's Common Equity
        Stop here.
        """

        items = {item.item_code: item for item in extract_items_from_text(text)}

        self.assertEqual(set(items), {"1", "1A", "1B", "1C", "2", "3", "4"})
        self.assertIn("We make products", items["1"].text)
        self.assertNotIn("Table of Contents", items["1"].text)
        self.assertIn("market, operational", items["1A"].text)

    def test_persist_extracted_items_replaces_unselected_items(self):
        html = """
        <html><body>
        <h2>Item 1. Business</h2><p>Business text.</p>
        <h2>Item 1A. Risk Factors</h2><p>Risk text.</p>
        <h2>Item 7. Management's Discussion and Analysis</h2><p>MD&A text.</p>
        <h2>Item 8. Financial Statements and Supplementary Data</h2><p>Financials.</p>
        </body></html>
        """

        persist_extracted_items(self.filing, html, item_codes=["1", "7"])
        self.assertEqual(list(self.filing.items.order_by("item_code").values_list("item_code", flat=True)), ["1", "7"])

        persist_extracted_items(self.filing, html, item_codes=["1A"])
        self.assertEqual(list(self.filing.items.order_by("item_code").values_list("item_code", flat=True)), ["1A"])


class FakeEmbeddingClient:
    model = "fake-embedding-model"
    deployment = ""

    def embed_documents(self, texts):
        return [[1.0, float(index)] for index, _ in enumerate(texts)]


class EmbeddingCompatibilityTests(TestCase):
    def test_embed_filing_chunks_returns_count_and_error(self):
        company = Company.objects.create(cik=320193, name="Apple Inc.", ticker="AAPL")
        filing = Filing.objects.create(
            company=company,
            accession_number="0000320193-24-000123",
            form_type="10-K",
            filing_date=date(2024, 11, 1),
            report_date=date(2024, 9, 28),
            fiscal_year=2024,
            sec_filing_url="https://example.com/raw.txt",
            sec_primary_doc_url="https://example.com/primary.htm",
        )
        filing.items.create(
            item_code="1A",
            title="Risk Factors",
            extracted_text=" ".join(f"risk sentence {index}" for index in range(80)),
            confidence=0.9,
        )

        created = create_chunks_for_filing(filing)
        count, error = embed_filing_chunks(filing, client=FakeEmbeddingClient())

        self.assertEqual(error, "")
        self.assertEqual(count, len(created))
        self.assertEqual(filing.chunks.filter(embedding__isnull=False).count(), len(created))

    def test_hugging_face_parser_mean_pools_batched_token_embeddings(self):
        parsed = HuggingFaceEmbeddingClient._parse_embeddings(
            [
                [[1.0, 3.0], [3.0, 5.0]],
                [[2.0, 4.0], [4.0, 6.0]],
            ]
        )

        self.assertEqual(parsed, [[2.0, 4.0], [3.0, 5.0]])
