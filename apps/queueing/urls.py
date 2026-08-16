from rest_framework.routers import DefaultRouter

from apps.queueing.views import QueueViewSet

app_name = "queueing"

router = DefaultRouter()
router.register("queue", QueueViewSet, basename="queue")

urlpatterns = router.urls
