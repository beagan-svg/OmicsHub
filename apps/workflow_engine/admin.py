from django.contrib import admin

from apps.workflow_engine.models import WorkflowConfig


@admin.register(WorkflowConfig)
class WorkflowConfigAdmin(admin.ModelAdmin):
    list_display = ["name", "uploaded_by", "uploaded_at", "is_active"]
    # No list_select_related, deliberately: left unset, Django select_related()s every
    # foreign key in list_display by itself, so `uploaded_by` is already joined. Naming a
    # list here replaces that blanket with exactly what is named, which is how a partial
    # list becomes an N+1 rather than a fix for one.
    list_filter = ["is_active"]
    readonly_fields = ["raw", "data", "uploaded_by", "uploaded_at", "is_active"]
    actions = ["activate"]

    def has_add_permission(self, request):
        # Configs are uploaded through the API so they are parsed and validated first.
        return False

    def has_delete_permission(self, request, obj=None):
        # apps/submission_queue reads the active config on every queue tick; deleting it stops
        # every submission with nothing to point at.
        return not (obj is not None and obj.is_active)

    @admin.action(description="Activate the selected config")
    def activate(self, request, queryset):
        configs = list(queryset[:2])
        if len(configs) != 1:
            self.message_user(request, "Select exactly one config to activate.", level="ERROR")
            return
        config = configs[0]
        config.activate()
        self.message_user(request, f"{config.name} is now the active config.")
