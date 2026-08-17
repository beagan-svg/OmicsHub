from rest_framework.routers import DefaultRouter

from apps.workflow_engine.views import WorkflowConfigViewSet

app_name = "workflow_engine"

router = DefaultRouter()
router.register("configs", WorkflowConfigViewSet, basename="workflowconfig")

urlpatterns = router.urls
