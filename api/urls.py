from rest_framework.routers import DefaultRouter

from . import *

router = DefaultRouter(trailing_slash="")  # No trailing slash
router.register(r"user", UserViewSet, "user")
router.register(r"product", ProductViewSet, "product")
router.register(r"category", CategoryViewSet, "category")

urlpatterns = router.urls
