import logging, stripe
from django.conf import settings
from rest_framework.response import Response
from rest_framework import viewsets
from base.models import OrderModel
from base.enums import ORDER_STATUS
from api.serializers import OrderSerializer, AddressSerializer, ShippingVendorSerializer

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
    "processing": "processing", 
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
            logger.error(f"Failed to retrieve PaymentIntent {pi} for status check: {e}", exc_info=True)
            return Response({"error": "Payment intent not found"}, status=400)

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

        # Find order in database using PaymentIntent ID lookup
        order = None
        try:
            # Use PaymentIntent ID
            order = OrderModel.objects.filter(paymentIntentId=pi).first()
            if order:
                logger.debug(f"Found order {order.id} via PaymentIntent ID for PI {pi}")
        except Exception as e:
            logger.error(f"Error querying order for PI {pi}: {e}", exc_info=True)

        # If order exists in database, use that status
        if order:
            order_status = _ORDER_STATUS_MAP.get(order.status, "pending")
            amount = int(order.totalPrice * 100)  # Convert to cents
            currency = "aud"  # TODO: get from order or settings
            
            # Serialize the complete order with all related data
            order_serializer = OrderSerializer(order)
            address_serializer = AddressSerializer(order.address)
            shipping_serializer = ShippingVendorSerializer(order.shippingVendor)
            
            data = {
                "status": order_status,
                "amount": amount,
                "currency": currency,
                "orderId": order.id,
                "order": order_serializer.data,
                "address": address_serializer.data,
                "shippingVendor": shipping_serializer.data,
            }
            return Response(data)

        # Check Stripe payment status
        stripe_status = _STRIPE_STATUS_MAP.get(intent.get("status"), "pending")
        amount = intent.get("amount_received") or intent.get("amount") or 0
        currency = (intent.get("currency") or "aud").lower()
        failure = intent.get("last_payment_error") or {}
        reason = failure.get("message") or failure.get("code")

        # payment succeeded but webhook hasn't processed yet:
        if stripe_status == "paid":
            order_id_in_metadata = (intent.get("metadata") or {}).get("order_id")
            if not order_id_in_metadata:
                # Payment succeeded but webhook hasn't created order yet
                # Return "processing" to indicate payment success but order creation pending
                stripe_status = "processing"
                logger.info(f"Payment succeeded for PI {pi} but order not created yet. Webhook processing.")

        data = {
            "status": stripe_status,
            "amount": amount,
            "currency": currency,
            "orderId": None,
        }
        if stripe_status == "failed" and reason:
            data["reason"] = reason

        return Response(data)