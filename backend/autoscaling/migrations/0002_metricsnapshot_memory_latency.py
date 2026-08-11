from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("autoscaling", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="metricsnapshot",
            name="latency",
            field=models.FloatField(default=120.0),
        ),
        migrations.AddField(
            model_name="metricsnapshot",
            name="memory",
            field=models.FloatField(default=50.0),
        ),
    ]
