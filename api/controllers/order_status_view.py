import logging, stripe
from django.conf import settings
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework.decorators import action

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY
GUEST_COOKIE = "guest_id"

_STATUS_MAP = {
    "succeeded": "paid",
    "processing": "pending",
    "requires_action": "pending",
    "requires_capture": "pending",
    "requires_confirmation": "pending",
    "requires_payment_method": "failed",
    "canceled": "failed",
}

class OrderStatusViewSet(viewsets.ViewSet):
    """
    Route:
      GET /api/orderstatus/status?pi=...
    """

    @action(detail=False, methods=["get"], url_path="status")
    def status(self, request):
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

        norm = _STATUS_MAP.get(intent.get("status"), "pending")
        amount = intent.get("amount_received") or intent.get("amount") or 0
        currency = (intent.get("currency") or "aud").lower()
        failure = intent.get("last_payment_error") or {}
        reason = failure.get("message") or failure.get("code")

        data = {
            "status": norm,
            "amount": amount,
            "currency": currency,
            "orderId": None,
        }
        if norm == "failed" and reason:
            data["reason"] = reason

        return Response(data)
