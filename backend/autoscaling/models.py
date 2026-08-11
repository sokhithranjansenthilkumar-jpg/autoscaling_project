from django.db import models


class MetricSnapshot(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    active_users = models.PositiveIntegerField()
    cpu = models.FloatField()
    memory = models.FloatField(default=50.0)
    latency = models.FloatField(default=120.0)
    current_instances = models.PositiveIntegerField(null=True, blank=True)
    source = models.CharField(max_length=50, default="manual")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.created_at.isoformat()} | cpu={self.cpu} | "
            f"users={self.active_users} | memory={self.memory} | "
            f"latency={self.latency} | instances={self.current_instances}"
        )


class ScenarioPreset(models.Model):
    group_name = models.CharField(max_length=100, db_index=True)
    row_number = models.PositiveIntegerField()
    active_users = models.PositiveIntegerField()
    cpu = models.FloatField()
    memory = models.FloatField()
    latency = models.FloatField()

    class Meta:
        ordering = ["group_name", "row_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["group_name", "row_number"],
                name="unique_scenario_group_row",
            )
        ]

    def __str__(self):
        return (
            f"{self.group_name} #{self.row_number} | users={self.active_users} | "
            f"cpu={self.cpu} | memory={self.memory} | latency={self.latency}"
        )
