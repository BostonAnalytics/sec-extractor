from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("filings", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FilingChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chunk_index", models.PositiveIntegerField()),
                ("item_code", models.CharField(max_length=3)),
                ("text", models.TextField()),
                ("start_offset", models.PositiveIntegerField()),
                ("end_offset", models.PositiveIntegerField()),
                ("embedding", models.JSONField(blank=True, null=True)),
                ("embedding_model", models.CharField(blank=True, max_length=255)),
                ("embedding_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "filing",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chunks", to="filings.filing"),
                ),
                (
                    "item",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chunks", to="filings.filingitem"),
                ),
            ],
            options={
                "ordering": ["filing", "item_code", "chunk_index"],
                "constraints": [models.UniqueConstraint(fields=("filing", "item_code", "chunk_index"), name="unique_filing_chunk")],
            },
        ),
    ]
