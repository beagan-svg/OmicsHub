from django.contrib import admin
from django.db.models import Exists, OuterRef

from apps.queueing.models import QueueEntry


@admin.register(QueueEntry)
class QueueEntryAdmin(admin.ModelAdmin):
    list_display = ["sample", "stage", "requested_by", "modality", "status", "created_at", "submitted_at"]
    list_filter = ["status", "stage", "modality", ("requested_by", admin.RelatedOnlyFieldListFilter)]
    # Every foreign key `list_display` dereferences has to be named: an explicit list
    # replaces the select_related() Django would otherwise apply to all of them, so
    # dropping one from here reintroduces a query per row for it.
    list_select_related = ["sample", "requested_by"]
    search_fields = ["sample__fastq_name", "demand_id"]
    readonly_fields = ["command", "command_args", "demand_id", "created_at", "claimed_at", "submitted_at"]
    autocomplete_fields = ["sample"]
    actions = ["cancel_entries", "requeue_entries"]

    @admin.action(description="Cancel selected pending entries")
    def cancel_entries(self, request, queryset):
        cancelled = queryset.filter(status=QueueEntry.Status.PENDING).update(
            status=QueueEntry.Status.CANCELLED
        )
        self.message_user(request, f"Cancelled {cancelled} pending entries.")

    @admin.action(description="Return selected failed or cancelled entries to the queue")
    def requeue_entries(self, request, queryset):
        # Submitted entries are deliberately excluded: they have a demand at OCS, and
        # requeueing one would run the same job twice. Stranded entries are excluded for
        # the same reason — nobody knows yet whether they reached OCS, so they are requeued
        # one at a time from the change form, after checking.
        #
        # Entries whose sample and stage are already waiting are excluded too, or the
        # update violates `one_pending_entry_per_sample_stage` and the whole action fails
        # having requeued nothing. Selecting an old failure alongside its live retry is the
        # ordinary way to hit that.
        already_pending = QueueEntry.objects.filter(
            status=QueueEntry.Status.PENDING,
            sample_id=OuterRef("sample_id"),
            stage=OuterRef("stage"),
        )
        eligible = queryset.filter(
            status__in=[QueueEntry.Status.FAILED, QueueEntry.Status.CANCELLED]
        ).exclude(Exists(already_pending))

        requeued = QueueEntry.objects.filter(pk__in=list(eligible.values_list("pk", flat=True))).update(
            status=QueueEntry.Status.PENDING, error_message=""
        )
        self.message_user(request, f"Returned {requeued} entries to the queue.")
