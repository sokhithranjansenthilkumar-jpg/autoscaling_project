from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="MetricSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("active_users", models.PositiveIntegerField()),
                ("cpu", models.FloatField()),
                ("current_instances", models.PositiveIntegerField(blank=True, null=True)),
                ("source", models.CharField(default="manual", max_length=50)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
