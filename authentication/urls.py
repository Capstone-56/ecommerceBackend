from rest_framework.routers import DefaultRouter

from . import *

router = DefaultRouter(trailing_slash="")  # No trailing slash
router.register(r"", AuthenticationViewSet, basename="")

urlpatterns = router.urls
