import logging, stripe
from django.conf import settings
from rest_framework.response import Response
from rest_framework import viewsets
from base.models import OrderModel, UserModel, GuestUserModel
from base.enums import ORDER_STATUS

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY
GUEST_COOKIE = "guest_id"

# Map our order status to frontend status
_ORDER_STATUS_MAP = {
    ORDER_STATUS.PENDING.value: "pending",
    ORDER_STATUS.PROCESSING.value: "paid",
    ORDER_STATUS.SHIPPED.value: "paid", 
    ORDER_STATUS.DELIVERED.value: "paid",
    ORDER_STATUS.CANCELLED.value: "failed",
}

# Fallback Stripe status mapping for when order doesn't exist yet
_STRIPE_STATUS_MAP = {
    "succeeded": "paid",
    "processing": "pending",
    "requires_action": "pending",
    "requires_capture": "pending",
    "requires_confirmation": "pending",
    "requires_payment_method": "failed",
    "canceled": "failed",
}

class OrderStatusViewSet(viewsets.ViewSet):
    def list(self, request):
        """
        GET /api/orderstatus?pi=...
        - A PaymentIntent is Stripe's object that holds information about a payment
        attempt, from creation to completion or failure.
        - Eg (simplified):
        - {
        "id": "pi_xxxxxxxxxxxxxxxxxxxxxxxx",
        "object": "payment_intent",
        "amount": 4999,
        "currency": "aud",
        "status": "requires_payment_method",
        "client_secret": "pi_xxxxxxxxxxxxxxxxxx_secret_ABCD1234",
        "metadata": {
            "order_id": "6735"
        },
        "shipping": {
            "name": "John Doe",
            "address": {
            "line1": "1 Street Street",
            "city": "Melbourne",
            "state": "VIC",
            "postal_code": "3000",
            "country": "AU"
            }
        }
        }
        """
        pi = request.query_params.get("pi")
        if not pi:
            return Response({"error": "missing pi"}, status=400)

        try:
            intent = stripe.PaymentIntent.retrieve(pi)
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=400)

        meta = intent.get("metadata") or {}
        user = getattr(request, "user", None)
        is_authed = bool(user and getattr(user, "is_authenticated", False))
        owner_user_id = (meta.get("user_id") or "").strip()
        owner_guest_id = (meta.get("guest_id") or "").strip()

        if is_authed:
            if owner_user_id and owner_user_id != str(user.id):
                return Response({"error": "forbidden"}, status=403)
        else:
            if owner_user_id:
                return Response({"error": "forbidden"}, status=403)
            if owner_guest_id:
                gid = request.COOKIES.get(GUEST_COOKIE)
                if not gid or gid != owner_guest_id:
                    return Response({"error": "forbidden"}, status=403)

        # find order in database
        order = None
        try:
            from django.utils import timezone
            from datetime import timedelta
            from decimal import Decimal
            
            # Get PaymentIntent amount for matching
            pi_amount_cents = intent.get("amount") or 0
            pi_amount_dollars = Decimal(str(pi_amount_cents / 100))
            
            if is_authed and owner_user_id:
                # Look for recent authenticated user orders with matching total
                recent_orders = OrderModel.objects.filter(
                    user_id=owner_user_id,
                    createdAt__gte=timezone.now() - timedelta(hours=1),
                    totalPrice=pi_amount_dollars
                ).order_by('-createdAt')
                
                order = recent_orders.first()
                
            elif owner_guest_id:
                # Look for recent guest orders with matching total
                recent_orders = OrderModel.objects.filter(
                    guestUser__guest_id=owner_guest_id,
                    createdAt__gte=timezone.now() - timedelta(hours=1),
                    totalPrice=pi_amount_dollars
                ).order_by('-createdAt')
                
                order = recent_orders.first()
                
        except Exception as e:
            logger.warning(f"Error querying order for PI {pi}: {e}")

        # If order exists in database, use that status
        if order:
            order_status = _ORDER_STATUS_MAP.get(order.status, "pending")
            amount = int(order.total_price * 100)  # Convert to cents
            currency = "aud"  # TODO: get from order or settings
            
            data = {
                "status": order_status,
                "amount": amount,
                "currency": currency,
                "orderId": order.id,
            }
            return Response(data)

        # Fallback to Stripe status if order doesn't exist yet
        stripe_status = _STRIPE_STATUS_MAP.get(intent.get("status"), "pending")
        amount = intent.get("amount_received") or intent.get("amount") or 0
        currency = (intent.get("currency") or "aud").lower()
        failure = intent.get("last_payment_error") or {}
        reason = failure.get("message") or failure.get("code")

        data = {
            "status": stripe_status,
            "amount": amount,
            "currency": currency,
            "orderId": None,
        }
        if stripe_status == "failed" and reason:
            data["reason"] = reason

        return Response(data)