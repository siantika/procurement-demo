import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("optimization", "0001_initial"),
        ("sourcing", "0002_procurementresult_procurementresultitem_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameField(
                    model_name="procurementresult",
                    old_name="optimization_run_id",
                    new_name="optimization_run",
                ),
                migrations.AlterField(
                    model_name="procurementresult",
                    name="optimization_run",
                    field=models.UUIDField(
                        blank=True,
                        db_column="optimization_run_id",
                        null=True,
                    ),
                ),
            ],
            database_operations=[],
        ),
        migrations.AlterField(
            model_name="procurementresult",
            name="optimization_run",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="procurement_results",
                to="optimization.optimizationrun",
            ),
        ),
    ]
