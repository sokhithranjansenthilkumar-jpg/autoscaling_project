from django.db import migrations, models


def seed_scenario_presets(apps, schema_editor):
    ScenarioPreset = apps.get_model("autoscaling", "ScenarioPreset")

    groups = [
        ("Quiet traffic", {"active_users": 120, "cpu": 34, "memory": 40, "latency": 82}),
        ("Sale hour", {"active_users": 420, "cpu": 78, "memory": 74, "latency": 190}),
        ("Weekend rush", {"active_users": 610, "cpu": 84, "memory": 79, "latency": 215}),
        ("Peak spike", {"active_users": 880, "cpu": 94, "memory": 91, "latency": 310}),
        ("Flash crowd", {"active_users": 1040, "cpu": 97, "memory": 94, "latency": 360}),
    ]

    rows = []
    for group_name, values in groups:
        for row_number in range(1, 11):
            rows.append(
                ScenarioPreset(
                    group_name=group_name,
                    row_number=row_number,
                    active_users=values["active_users"],
                    cpu=values["cpu"],
                    memory=values["memory"],
                    latency=values["latency"],
                )
            )

    ScenarioPreset.objects.bulk_create(rows)


def unseed_scenario_presets(apps, schema_editor):
    ScenarioPreset = apps.get_model("autoscaling", "ScenarioPreset")
    ScenarioPreset.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("autoscaling", "0002_metricsnapshot_memory_latency"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScenarioPreset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("group_name", models.CharField(db_index=True, max_length=100)),
                ("row_number", models.PositiveIntegerField()),
                ("active_users", models.PositiveIntegerField()),
                ("cpu", models.FloatField()),
                ("memory", models.FloatField()),
                ("latency", models.FloatField()),
            ],
            options={
                "ordering": ["group_name", "row_number"],
            },
        ),
        migrations.AddConstraint(
            model_name="scenariopreset",
            constraint=models.UniqueConstraint(
                fields=("group_name", "row_number"),
                name="unique_scenario_group_row",
            ),
        ),
        migrations.RunPython(seed_scenario_presets, unseed_scenario_presets),
    ]
