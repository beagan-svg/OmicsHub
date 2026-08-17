"""Intentionally empty.

A `GeneratedField` cannot be altered in place — Django requires the column to be dropped
and re-added — so the expressions on `Sample.batch_prefix` and `Sample.modality` were left
exactly as 0004 created them, and the reorganisation that produced this migration was
reverted in the model instead.

The file is kept, rather than deleted, because `queueing.0004_cartitem` already depends on
this node. Removing it breaks the migration graph for anyone who has that migration.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0004_sample_batch_prefix_sample_modality_and_more"),
    ]

    operations = []
