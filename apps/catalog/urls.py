from rest_framework.routers import DefaultRouter

from apps.catalog.views import SampleViewSet

app_name = "catalog"

router = DefaultRouter()
router.register("samples", SampleViewSet, basename="sample")

urlpatterns = router.urls
