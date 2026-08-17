from rest_framework.routers import DefaultRouter

from apps.submission_queue.views import QueueViewSet

app_name = "submission_queue"

router = DefaultRouter()
router.register("queue", QueueViewSet, basename="queue")

urlpatterns = router.urls
