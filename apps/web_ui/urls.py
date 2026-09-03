from django.urls import path
from django.views.generic import RedirectView

from apps.web_ui.views.configs import activate_config, config_detail, configs
from apps.web_ui.views.dashboard import (
    cart_add,
    cart_clear,
    cart_remove,
    dashboard,
    export_csv,
    live_status,
    refresh_status,
    set_columns,
    sync_samples,
)
from apps.web_ui.views.data_locations import (
    data_location_contents,
    data_locations,
    download_data_location_files,
    export_data_locations_csv,
)
from apps.web_ui.views.monitor import (
    delete_job,
    failed_jobs,
    job_credentials_clear,
    job_credentials_status,
    job_credentials_submit,
    job_demand_logs,
    job_monitor,
    retry_job,
)
from apps.web_ui.views.queue import cancel, delete_queue_entry, queue, toggle_queue_pause
from apps.web_ui.views.submissions import (
    checkout,
    command_preview,
    submit_commands,
    submit_confirm,
    submit_review,
)
from apps.web_ui.views.timeline import job_timeline

app_name = "web_ui"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("data-locations/", data_locations, name="data-locations"),
    path("data-locations/export/", export_data_locations_csv, name="data-locations-export"),
    path(
        "data-locations/<int:sample_id>/<str:stage>/contents/",
        data_location_contents,
        name="data-location-contents",
    ),
    path(
        "data-locations/<int:sample_id>/<str:stage>/download/",
        download_data_location_files,
        name="data-location-download",
    ),
    path("sync/", sync_samples, name="sync"),
    path("live-status/", live_status, name="live-status"),
    path("status/refresh/", refresh_status, name="refresh-status"),
    path("columns/", set_columns, name="set-columns"),
    path("export/", export_csv, name="export"),
    path("cart/add/", cart_add, name="cart-add"),
    path("cart/remove/", cart_remove, name="cart-remove"),
    path("cart/clear/", cart_clear, name="cart-clear"),
    path("checkout/", checkout, name="checkout"),
    path("submit/review/", submit_review, name="submit-review"),
    path("submit/preview/", command_preview, name="command-preview"),
    path("submit/commands/", submit_commands, name="submit-commands"),
    path("submit/confirm/", submit_confirm, name="submit-confirm"),
    path("queue/", queue, name="queue"),
    path("queue/pause/", toggle_queue_pause, name="toggle-queue-pause"),
    path("queue/<int:pk>/cancel/", cancel, name="cancel"),
    path("queue/<int:pk>/delete/", delete_queue_entry, name="delete-queue-entry"),
    path("monitor/", job_monitor, name="job-monitor"),
    path("timeline/", job_timeline, name="job-timeline"),
    path("monitor/credentials/", job_credentials_submit, name="job-credentials-submit"),
    path("monitor/credentials/status/", job_credentials_status, name="job-credentials-status"),
    path("monitor/credentials/clear/", job_credentials_clear, name="job-credentials-clear"),
    path("monitor/<str:demand_id>/logs/", job_demand_logs, name="job-demand-logs"),
    path("failed/", failed_jobs, name="failed"),
    path("failed/<int:pk>/retry/", retry_job, name="retry"),
    path("failed/<int:pk>/delete/", delete_job, name="delete-job"),
    # Configs is where the config lives. The old /settings/ path is kept so links and
    # bookmarks from before the rename still land somewhere, rather than 404ing.
    path("configs/", configs, name="configs"),
    path("settings/", RedirectView.as_view(pattern_name="web_ui:configs", permanent=False)),
    path("configs/<int:pk>/", config_detail, name="config-detail"),
    path("configs/<int:pk>/activate/", activate_config, name="activate-config"),
]
