from decimal import Decimal, ROUND_HALF_UP
from django.apps import apps
from django.conf import settings
from django.db.models import Min
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import uuid
from typing import Tuple

import stripe

stripe.api_key = settings.STRIPE_SECRET_KEY

GUEST_COOKIE = "guest_id"
GUEST_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

# Hardcoded store currency for now
STORE_DEFAULT_CURRENCY = getattr(settings, "STORE_DEFAULT_CURRENCY", "aud").lower()

# converting dollars to cents for Stripe
def _to_cents(value: Decimal) -> int:
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def get_or_create_guest_id(request) -> Tuple[str, bool]:
    """Return (guest_id, is_new)."""
    gid = request.COOKIES.get(GUEST_COOKIE)
    if gid:
        return gid, False
    return str(uuid.uuid4()), True

from decimal import Decimal, ROUND_HALF_UP
from django.apps import apps
from django.db.models import Min
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
import stripe

def _to_cents(value: Decimal) -> int:
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

# need to eventually store cart in database
class CreateIntentView(APIView):
    # guests allowed to checkout
    permission_classes = [AllowAny]

    def post(self, request):
        body = request.data if hasattr(request, "data") else {}
        cart = body.get("cart") or []
        if not isinstance(cart, list) or not cart:
            return Response({"error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)

        # Normalise cart & collect product ids
        product_ids: list[str] = []
        lines_norm: list[dict] = []
        for line in cart:
            qty = int(line.get("quantity") or 0)
            pid = (line.get("product") or {}).get("id")
            if not pid or qty <= 0:
                continue
            pid = str(pid)
            product_ids.append(pid)
            lines_norm.append({"product_id": pid, "qty": qty})
        if not lines_norm:
            return Response({"error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)

        ProductItemModel = apps.get_model("base", "ProductItemModel")
        ProductModel = apps.get_model("base", "ProductModel")

        price_by_product: dict[str, Decimal] = {}
        name_by_product: dict[str, str] = {}

        price_rows = (
            ProductItemModel.objects
            .filter(product_id__in=product_ids)
            .values("product_id")
            .annotate(unit_price=Min("price"))
        )
        for r in price_rows:
            price_by_product[str(r["product_id"])] = Decimal(str(r["unit_price"]))

        name_rows = ProductModel.objects.filter(id__in=product_ids).values("id", "name")
        for r in name_rows:
            name_by_product[str(r["id"])] = r["name"] or "Product"

        # sum + build summary for OrderComplete
        missing_products: list[str] = []
        total = Decimal("0")
        items_summary: list[dict] = []

        for nl in lines_norm:
            pid, qty = nl["product_id"], nl["qty"]
            unit = price_by_product.get(pid, Decimal("0"))
            if unit <= 0:
                missing_products.append(pid)
                continue
            subtotal = unit * qty
            total += subtotal
            items_summary.append({
                "id": pid,
                "kind": "product",
                "name": name_by_product.get(pid, "Product"),
                "quantity": qty,
                "unit_price_cents": _to_cents(unit),
                "subtotal_cents": _to_cents(subtotal),
            })

        if missing_products:
            return Response(
                {"error": "Some products have no priced variants", "missingProductIds": missing_products},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount_cents = _to_cents(total)
        if amount_cents <= 0:
            return Response({"error": "Cart is empty or invalid"}, status=status.HTTP_400_BAD_REQUEST)

        user = getattr(request, "user", None)
        is_authed = bool(user and getattr(user, "is_authenticated", False))

        guest_id, is_new = (None, False)
        if not is_authed:
            guest_id, is_new = get_or_create_guest_id(request)

        # Create PI
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=STORE_DEFAULT_CURRENCY,
                automatic_payment_methods={"enabled": True},
                metadata={
                    "user_id": str(request.user.id) if is_authed else "",
                    "guest_id": guest_id if not is_authed else "",
                }
            )
            payload = {
                "clientSecret": intent.client_secret,
                "intentId": intent.id,
                "currency": STORE_DEFAULT_CURRENCY,
                "total_cents": amount_cents,
                "items": items_summary,
            }
            resp = Response(payload)

            # Set cookie for guests
            if (not is_authed) and guest_id:
                resp.set_cookie(
                    key=GUEST_COOKIE,
                    value=guest_id,
                    max_age=GUEST_COOKIE_MAX_AGE,
                    httponly=True,
                    samesite="Lax",
                    secure=False,  # change to True on HTTPS
                )
            return resp
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=400)


class UpdateIntentShippingView(APIView):
    permission_classes = [AllowAny]

    def put(self, request, intent_id: str):
        try:
            pi = stripe.PaymentIntent.retrieve(intent_id)
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=400)

        meta = pi.get("metadata") or {}
        user = getattr(request, "user", None)
        is_authed = bool(user and getattr(user, "is_authenticated", False))
        is_owner = False

        if is_authed and meta.get("user_id") == str(user.id):
            is_owner = True
        else:
            gid = request.COOKIES.get(GUEST_COOKIE)
            if gid and gid == meta.get("guest_id"):
                is_owner = True

        if not is_owner:
            return Response({"error": "forbidden"}, status=403)

        body = request.data or {}
        shipping = body.get("shipping") or {}
        name = body.get("name") or shipping.get("name") or ""
        
        try:
            stripe.PaymentIntent.modify(
                intent_id,
                shipping={
                    "name": name,
                    "address": {
                        "line1": shipping.get("line1", ""),
                        "line2": shipping.get("line2"),
                        "city": shipping.get("city", ""),
                        "state": shipping.get("state"),
                        "postal_code": shipping.get("postal_code", ""),
                        "country": shipping.get("country", ""),
                    },
                    "phone": shipping.get("phone"),
                },
            )
            return Response(status=status.HTTP_204_NO_CONTENT)
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=400)


# need to eventually use webhook as source of truth for payment status
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        # TODO: Process successful payment (create order, send confirmation email, whatever...)
        pass

    return HttpResponse(status=200)
