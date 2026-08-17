from django.urls import path
from django.views.generic import RedirectView

from apps.web_ui import views

app_name = "web_ui"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("sync/", views.sync_samples, name="sync"),
    path("status/refresh/", views.refresh_status, name="refresh-status"),
    path("columns/", views.set_columns, name="set-columns"),
    path("export/", views.export_csv, name="export"),
    path("cart/add/", views.cart_add, name="cart-add"),
    path("cart/remove/", views.cart_remove, name="cart-remove"),
    path("cart/clear/", views.cart_clear, name="cart-clear"),
    path("checkout/", views.checkout, name="checkout"),
    path("submit/review/", views.submit_review, name="submit-review"),
    path("submit/preview/", views.command_preview, name="command-preview"),
    path("submit/commands/", views.submit_commands, name="submit-commands"),
    path("submit/confirm/", views.submit_confirm, name="submit-confirm"),
    path("queue/", views.queue, name="queue"),
    path("queue/<int:pk>/cancel/", views.cancel, name="cancel"),
    path("jobs/", views.job_monitor, name="job-monitor"),
    path("failed/", views.failed_jobs, name="failed"),
    path("failed/<int:pk>/retry/", views.retry_job, name="retry"),
    path("failed/<int:pk>/delete/", views.delete_job, name="delete-job"),
    # Settings is where the config lives now. The old /configs/ path is kept so links and
    # bookmarks from before the rename still land somewhere, rather than 404ing.
    path("settings/", views.configs, name="configs"),
    path("configs/", RedirectView.as_view(pattern_name="web_ui:configs", permanent=False)),
    path("settings/<int:pk>/activate/", views.activate_config, name="activate-config"),
]
