from rest_framework.routers import DefaultRouter

from apps.workflows.views import WorkflowConfigViewSet

app_name = "workflows"

router = DefaultRouter()
router.register("configs", WorkflowConfigViewSet, basename="workflowconfig")

urlpatterns = router.urls
