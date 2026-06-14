from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("filings", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChatMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("user", "User"), ("assistant", "Assistant")], max_length=16)),
                ("message", models.TextField()),
                ("citations", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "filing",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chat_messages", to="filings.filing"),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
    ]
