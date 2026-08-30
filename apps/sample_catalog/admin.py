from django.contrib import admin

from apps.sample_catalog.models import Sample, StageStatus


class StageStatusInline(admin.TabularInline):
    # SampleAdmin.has_change_permission is False, which already renders this inline
    # read-only; only the blank rows have to be turned off explicitly.
    model = StageStatus
    extra = 0


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    """Prevent edits because this table stores synced OCS data."""

    list_display = [
        "fastq_name",
        "batch_name_from_vendor",
        "organism_common_name",
        "library_prep_method_name",
        "synced_at",
    ]
    list_filter = ["organism_common_name", "library_prep_method_name"]
    search_fields = ["fastq_name", "batch_name_from_vendor", "load_name"]
    inlines = [StageStatusInline]

    # Half a million rows. Django otherwise runs a second, unfiltered COUNT(*) on every
    # filtered or searched page, only to print "(N total)" beside the result count. A full
    # scan of the whole local database for a number nobody acts on. The paginator's own count still
    # runs, so the page numbers stay real.
    show_full_result_count = False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Deleting a synced row achieves nothing a re-sync would not undo, and queue
        # entries reference it. The only effect would be a ProtectedError or, worse,
        # confusion about where a sample went.
        return False
