from rest_framework.routers import DefaultRouter

from .controllers import *

router = DefaultRouter(trailing_slash="")  # No trailing slash
router.register(r"user", UserViewSet, "user")
router.register(r"product", ProductViewSet, "product")
router.register(r"category", CategoryViewSet, "category")
router.register(r"address", AddressViewSet, "address")
router.register(r"cart", ShoppingCartViewSet, "cart")
router.register(r"productItem", ProductItemViewSet, "productItem")
router.register(r"stripe", StripeViewSet, "stripe")
router.register(r"orderstatus", OrderStatusViewSet, "orderstatus")
router.register(r"location", LocationViewSet, "location")

urlpatterns = router.urls
