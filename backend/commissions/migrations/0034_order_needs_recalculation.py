from django.db import migrations, models


def ensure_needs_recalculation_column(apps, schema_editor):
    """Column may already exist in DB without a default — normalize it."""
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'commissions_order'
              AND column_name = 'needs_recalculation'
            """
        )
        if cursor.fetchone():
            cursor.execute(
                """
                UPDATE commissions_order
                SET needs_recalculation = FALSE
                WHERE needs_recalculation IS NULL
                """
            )
            cursor.execute(
                """
                ALTER TABLE commissions_order
                ALTER COLUMN needs_recalculation SET DEFAULT FALSE
                """
            )
            cursor.execute(
                """
                ALTER TABLE commissions_order
                ALTER COLUMN needs_recalculation SET NOT NULL
                """
            )
        else:
            cursor.execute(
                """
                ALTER TABLE commissions_order
                ADD COLUMN needs_recalculation boolean NOT NULL DEFAULT FALSE
                """
            )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS commissions_order_needs_recalculation_idx
            ON commissions_order (needs_recalculation)
            """
        )


class Migration(migrations.Migration):
    dependencies = [
        ("commissions", "0033_alter_commissionrulecondition_field"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="order",
                    name="needs_recalculation",
                    field=models.BooleanField(
                        default=False,
                        db_index=True,
                        help_text="Set when order data changes and commission should be recalculated.",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    ensure_needs_recalculation_column,
                    migrations.RunPython.noop,
                ),
            ],
        ),
    ]
