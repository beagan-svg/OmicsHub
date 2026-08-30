from django.core.management.base import BaseCommand, CommandError

from apps.sample_catalog import ocs_sync as sync


class Command(BaseCommand):
    help = (
        "Refresh stage status by sweeping the demand registry and fastq-history. The "
        "registry carries work still in flight or failed; history carries what finished. "
        "Safe to re-run."
    )

    def handle(self, *args, **options):
        prefixes = sync.active_batch_prefixes()
        if prefixes is None:
            raise CommandError(sync.NO_ACTIVE_CONFIG)

        result = sync.sync_all_stage_statuses(batch_prefixes=prefixes)
        self.stdout.write(self.style.SUCCESS(f"Wrote {result['statuses']} stage statuses."))
        if result["discovered"]:
            self.stdout.write(f"  Discovered {result['discovered']} samples new to the local database.")
        if result["out_of_scope"]:
            self.stdout.write(
                f"  {result['out_of_scope']} skipped. Batch is outside the configured workflows."
            )
