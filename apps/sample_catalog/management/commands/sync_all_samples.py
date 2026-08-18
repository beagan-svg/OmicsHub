from django.core.management.base import BaseCommand, CommandError

from apps.sample_catalog import ocs_sync as sync


class Command(BaseCommand):
    help = (
        "Mirror OCS samples whose vendor batch prefix has "
        "a workflow in the active config. Samples outside that scope are pruned. Safe to "
        "re-run; stage status is refreshed separately by sync_stage_statuses."
    )

    def handle(self, *args, **options):
        prefixes = sync.active_batch_prefixes()
        if prefixes is None:
            raise CommandError(f"{sync.NO_ACTIVE_CONFIG} Upload and activate one first.")

        self.stdout.write(f"Mirroring batches for: {', '.join(sorted(prefixes))}")

        result = sync.sync_all_samples(
            batch_prefixes=prefixes,
            progress=lambda count: self.stdout.write(f"  {count} samples...", ending="\r"),
        )

        self.stdout.write(self.style.SUCCESS(f"Mirrored {result['mirrored']} samples."))
        if result["pruned"]:
            self.stdout.write(f"  Pruned {result['pruned']} now outside the configured workflows.")
