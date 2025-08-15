from rest_framework.routers import DefaultRouter
from django.urls import path

from .controllers import *
from .controllers.stripe_view import CreateIntentView, UpdateIntentShippingView, stripe_webhook
from .controllers.order_status_view import OrderStatusView

router = DefaultRouter(trailing_slash="")  # No trailing slash
router.register(r"user", UserViewSet, "user")
router.register(r"product", ProductViewSet, "product")
router.register(r"category", CategoryViewSet, "category")
router.register(r"address", AddressViewSet, "address")
router.register(r"cart", ShoppingCartViewSet, "cart")
router.register(r"productItem", ProductItemViewSet, "productItem")

urlpatterns = [
    *router.urls,
    path("payments/create-intent", CreateIntentView.as_view()),
    path("payments/<str:intent_id>/shipping", UpdateIntentShippingView.as_view()),
    path("orders/status", OrderStatusView.as_view()),
    path("payments/webhook", stripe_webhook),
]