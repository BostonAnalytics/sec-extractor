from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Company",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cik", models.PositiveBigIntegerField(unique=True)),
                ("name", models.CharField(max_length=255)),
                ("ticker", models.CharField(blank=True, max_length=32)),
                ("exchange", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["ticker", "name"], "verbose_name_plural": "companies"},
        ),
        migrations.CreateModel(
            name="Filing",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("accession_number", models.CharField(max_length=32, unique=True)),
                ("form_type", models.CharField(max_length=16)),
                ("filing_date", models.DateField()),
                ("report_date", models.DateField(blank=True, null=True)),
                ("fiscal_year", models.PositiveIntegerField(blank=True, null=True)),
                ("sec_filing_url", models.URLField(max_length=500)),
                ("sec_primary_doc_url", models.URLField(max_length=500)),
                ("raw_text_path", models.CharField(blank=True, max_length=500)),
                ("primary_document_path", models.CharField(blank=True, max_length=500)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("downloaded", "Downloaded"),
                            ("extracted", "Extracted"),
                            ("failed", "Failed"),
                        ],
                        default="new",
                        max_length=16,
                    ),
                ),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="filings", to="filings.company"),
                ),
            ],
            options={"ordering": ["-filing_date", "company__ticker"]},
        ),
        migrations.CreateModel(
            name="FilingItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("item_code", models.CharField(max_length=3)),
                ("title", models.CharField(max_length=255)),
                ("extracted_text", models.TextField()),
                ("start_offset", models.PositiveIntegerField(blank=True, null=True)),
                ("end_offset", models.PositiveIntegerField(blank=True, null=True)),
                ("confidence", models.FloatField(default=0.0)),
                ("warnings", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "filing",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="filings.filing"),
                ),
            ],
            options={
                "ordering": ["filing", "item_code"],
                "constraints": [models.UniqueConstraint(fields=("filing", "item_code"), name="unique_filing_item_code")],
            },
        ),
    ]
