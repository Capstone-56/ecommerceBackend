from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple
import uuid
import json
import stripe
import logging

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action

from base import Constants
from base.models import ProductItemModel, ProductLocationModel, ProductItemLocationModel

from api.services import OrderCreationService

stripe.api_key = settings.STRIPE_SECRET_KEY

GUEST_COOKIE = "guest_id"
GUEST_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

logger = logging.getLogger(__name__)

# Hardcoded store currency for now
STORE_DEFAULT_CURRENCY = getattr(settings, "STORE_DEFAULT_CURRENCY", "aud").lower()

# converting dollars to cents for Stripe
def _to_cents(value: Decimal) -> int:
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def get_or_create_guest_id(request) -> Tuple[str, bool]:
    gid = request.COOKIES.get(GUEST_COOKIE)
    if gid:
        return gid, False
    return str(uuid.uuid4()), True

class StripeViewSet(viewsets.ViewSet):
    @action(detail=False, methods=["post"], url_path="create-intent")
    def create_intent(self, request):
        """
        Creates a Stripe PaymentIntent for processing payments.
        
        Route: POST /api/stripe/create-intent
        
        Purpose:
        - Validates cart items and quantities from request
        - Fetches current product prices and stock levels from database
        - Validates stock availability for all requested quantities
        - Calculates total amount and creates line items summary
        - Creates Stripe PaymentIntent with automatic payment methods
        - Handles both authenticated users and guest checkouts
        - Sets guest cookie for anonymous users
        
        Request Body:
        {
            "cart": [
                {
                    "product": {"id": "product_id"},
                    "quantity": 2
                }
            ]
        }
        
        Returns:
        - Success: PaymentIntent client secret, intent ID, total, and items summary
        - Error: Validation errors for empty cart, missing products, insufficient stock, or Stripe errors
        """
        body = request.data if hasattr(request, "data") else {}
        cart = body.get("cart") or []
        if not isinstance(cart, list) or not cart:
            return Response(
                {"error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Normalise input, receiving ProductItem IDs
        product_item_ids: list[str] = []
        lines_norm: list[dict] = []
        for line in cart:
            qty = int(line.get("quantity") or 0)
            product_item_id = (line.get("product") or {}).get("id")
            if not product_item_id or qty <= 0:
                continue
            product_item_id = str(product_item_id)
            product_item_ids.append(product_item_id)
            lines_norm.append({"product_item_id": product_item_id, "qty": qty})
        if not lines_norm:
            return Response(
                {"error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Get user's country from request (query param, header, or body)
        country_code = (
            request.query_params.get("country") or 
            request.data.get("country") or 
            request.headers.get("X-Country-Code") or
            "AU"  # Default fallback
        )

        # Get pricing, names, and stock from ProductItem IDs directly
        price_by_product_item: dict[str, Decimal] = {}
        name_by_product_item: dict[str, str] = {}
        stock_by_product_item: dict[str, int] = {}

        # Query ProductItems directly by their IDs
        product_items = ProductItemModel.objects.filter(id__in=product_item_ids).select_related('product')
        
        # Get prices from ProductItemLocation (with discounts) or ProductLocation
        for item in product_items:
            price = 0.0
            name = "Product"
            
            # Try to get ProductItemLocation price (includes discounts)
            try:
                item_location = ProductItemLocationModel.objects.get(
                    productItem=item,
                    location__country_code=country_code
                )
                
                price = float(item_location.final_price)  # Uses discount if active

                # Get name from ProductLocation
                product_location = ProductLocationModel.objects.get(
                    product=item.product,
                    location__country_code=country_code
                )
                name = product_location.name
            except (ProductItemLocationModel.DoesNotExist, ProductLocationModel.DoesNotExist):
                # Fallback: Get base price from ProductLocation
                try:
                    product_location = ProductLocationModel.objects.get(
                        product=item.product,
                        location__country_code=country_code
                    )
                    price = float(product_location.price)
                    name = product_location.name
                except ProductLocationModel.DoesNotExist:
                    # Last resort: Use first available location
                    first_location = ProductLocationModel.objects.filter(product=item.product).first()
                    price = first_location.price if first_location else 0.0
                    name = first_location.name if first_location else "Product"
            
            price_by_product_item[str(item.id)] = Decimal(str(price))
            name_by_product_item[str(item.id)] = name
            stock_by_product_item[str(item.id)] = item.stock

        # Sum + prepare summary with stock validation
        missing_product_items: list[str] = []
        insufficient_stock_items: list[dict] = []
        total = Decimal("0")
        items_summary: list[dict] = []

        for nl in lines_norm:
            product_item_id, qty = nl["product_item_id"], nl["qty"]
            unit = price_by_product_item.get(product_item_id, Decimal("0"))
            stock = stock_by_product_item.get(product_item_id, 0)
            if unit <= 0:
                missing_product_items.append(product_item_id)
                continue
            
            # Check stock availability
            if stock < qty:
                insufficient_stock_items.append({
                    "productItemId": product_item_id,
                    "requested": qty,
                    "available": stock,
                    "name": name_by_product_item.get(product_item_id, "Product")
                })
                continue
                
            subtotal = unit * qty
            total += subtotal
            items_summary.append(
                {
                    "id": product_item_id,
                    "kind": "product",
                    "name": name_by_product_item.get(product_item_id, "Product"),
                    "quantity": qty,
                    "unit_price_cents": _to_cents(unit),
                    "subtotal_cents": _to_cents(subtotal),
                }
            )

        if missing_product_items:
            return Response(
                {
                    "error": "Some product items not found",
                    "missingProductItemIds": missing_product_items,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if insufficient_stock_items:
            return Response(
                {
                    "error": "Insufficient stock for some items",
                    "insufficientStockItems": insufficient_stock_items,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount_cents = _to_cents(total)
        if amount_cents <= 0:
            return Response(
                {"error": "Cart is empty or invalid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = getattr(request, "user", None)
        is_authed = bool(user and getattr(user, "is_authenticated", False))

        guest_id, is_new = (None, False)
        if not is_authed:
            guest_id, is_new = get_or_create_guest_id(request)

        # Store cart data in PaymentIntent metadata for order creation on payment success
        metadata = {
            "user_id": str(user.id) if is_authed else "",
            "guest_id": guest_id if not is_authed else "",
            "total_price": str(total),
            "is_authenticated": str(is_authed),
        }
        
        # For authed users, we can retrieve cart from database, no need to store in metadata
        # For guests, must store cart in metadata since they don't have persistent storage
        if not is_authed:
            cart_items_str = json.dumps([{"product_item_id": nl["product_item_id"], "qty": nl["qty"]} for nl in lines_norm])
            
            # Validate metadata size limits, stripe is 500 characters per key
            if len(cart_items_str) > 500:
                logger.warning(f"Guest cart metadata exceeds 500 characters ({len(cart_items_str)}). Using compressed format.")
                # Use more compact format for large guest carts
                cart_items_str = json.dumps([{"id": nl["product_item_id"], "q": nl["qty"]} for nl in lines_norm])
                
                # If still too large, reject the cart
                if len(cart_items_str) > 500:
                    logger.error(f"Guest cart too large for metadata ({len(cart_items_str)} chars)")
                    return Response(
                        {"error": "Cart is too large to process. Please reduce the number of items or create an account."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            metadata["cart_items"] = cart_items_str
        
        # Create PaymentIntent
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=STORE_DEFAULT_CURRENCY,
                automatic_payment_methods={"enabled": True},
                metadata=metadata,
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
                    samesite=Constants.CookiePolicy.SAME_SITE,
                    secure=True,
                )
            return resp
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create PaymentIntent: {e}", exc_info=True)
            return Response({"error": "Payment processing unavailable"}, status=400)

    @action(detail=True, methods=["put"], url_path="shipping")
    def shipping(self, request, pk=None):
        """
        Updates shipping information for a PaymentIntent.
        
        Route: PUT /api/stripe/{intent_id}/shipping
        
        Purpose:
        - Retrieves existing PaymentIntent from Stripe
        - Verifies user/guest ownership of the payment intent
        - Accepts shipping address and contact information
        - Stores shipping data for order fulfillment
        - Supports both authenticated users and guest checkouts
        
        URL Parameters:
        - intent_id: Stripe PaymentIntent ID
        
        Request Body:
        {
            "name": "Customer Name",
            "shipping": {
                "line1": "1 Street St",
                "line2": "",
                "city": "Melbourne",
                "state": "VIC",
                "postal_code": "3000",
                "country": "AU",
                "phone": "+61123456789"
            }
        }
        
        Returns:
        - Success: Confirmation message with intent ID
        - Error: Forbidden access or Stripe errors
        """
        intent_id = pk

        # Verify PaymentIntent exists and user has access
        try:
            pi = stripe.PaymentIntent.retrieve(intent_id)
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve PaymentIntent {intent_id}: {e}", exc_info=True)
            return Response({"error": "Payment intent not found"}, status=400)

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
        
        # Extract additional order data from request
        address_id = body.get("addressId") or shipping.get("addressId")
        shipping_vendor_id = body.get("shippingVendorId") or shipping.get("shippingVendorId")
        
        # For guests, collect user details if provided
        guest_email = body.get("email")
        guest_first_name = body.get("firstName") 
        guest_last_name = body.get("lastName")
        guest_phone = body.get("phone") or shipping.get("phone", "")

        # Update PaymentIntent metadata with shipping and order details
        updated_metadata = dict(pi.get("metadata", {}))
        updated_metadata.update({
            "shipping_name": name,
            "shipping_line1": shipping.get("line1", ""),
            "shipping_line2": shipping.get("line2", ""),
            "shipping_city": shipping.get("city", ""),
            "shipping_state": shipping.get("state", ""),
            "shipping_postal_code": shipping.get("postal_code", ""),
            "shipping_country": shipping.get("country", ""),
            "shipping_phone": guest_phone,
        })
        
        # Add order-specific data if provided
        if address_id:
            updated_metadata["address_id"] = str(address_id)
        if shipping_vendor_id:
            updated_metadata["shipping_vendor_id"] = str(shipping_vendor_id)
            
        # Add guest user details if provided
        if not is_authed and guest_email:
            # Safely parse name to avoid IndexError on empty strings
            name_parts = name.strip().split() if name and name.strip() else []
            
            # Use provided names or fallback to parsed name parts
            first_name = guest_first_name or (name_parts[0] if len(name_parts) > 0 else "")
            last_name = guest_last_name or (name_parts[-1] if len(name_parts) > 1 else "")
            
            updated_metadata.update({
                "guest_email": guest_email,
                "guest_first_name": first_name,
                "guest_last_name": last_name,
            })
        
        # Update the PaymentIntent with new metadata
        try:
            stripe.PaymentIntent.modify(intent_id, metadata=updated_metadata)
        except stripe.error.StripeError as e:
            logger.error(f"Failed to update PaymentIntent {intent_id} metadata: {e}", exc_info=True)
            return Response({"error": "Failed to update payment intent"}, status=400)

        return Response(
            {"message": "Shipping data received successfully", "intent_id": intent_id},
            status=status.HTTP_200_OK,
        )

    @method_decorator(csrf_exempt)  # stripe posts without CSRF token
    @action(
        detail=False,
        methods=["post"],
        url_path="webhook",
        authentication_classes=[],  # not needed for Stripe
    )
    def webhook(self, request):
        """
        Handles Stripe webhook events for payment processing.
        Route: POST /api/stripe/webhook
        
        Purpose:
        - Receives and verifies webhook events from Stripe
        - Processes payment_intent.succeeded events to create orders automatically
        - Validates stock availability and updates inventory levels
        - Creates orders from PaymentIntent metadata for both authenticated and guest users
        - Updates order status to PROCESSING and stores order ID in PaymentIntent metadata

        Webhook Events Handled:
        - payment_intent.succeeded: Validates stock, creates order, updates inventory, and clears user cart
        - payment_intent.payment_failed: Logs payment failure

        Authentication:
        - Uses Stripe signature verification instead of Django auth
        - CSRF exempt as Stripe doesn't send CSRF tokens

        Returns:
        - 200 OK: Event processed successfully
        - 400 Bad Request: Invalid signature or malformed payload

        Note: Requires STRIPE_WEBHOOK_SECRET to be configured in settings
        """
        # raw body for signature verification
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=settings.STRIPE_WEBHOOK_SECRET,
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response(status=400)

        etype = event.get("type")
        obj = event.get("data", {}).get("object", {})
        
        if etype == "payment_intent.succeeded":
            # Create order from successful payment
            payment_intent_id = obj.get('id')
            try:
                order = OrderCreationService.create_order_from_payment_intent(obj)
                if order:
                    logger.info(f"Webhook: Successfully created order {order.id} for PaymentIntent {payment_intent_id}")
                else:
                    logger.error(f"Webhook: Failed to create order for PaymentIntent {payment_intent_id} - check validation requirements")
                    # Don't return error - webhook should still return 200 to Stripe to prevent retries
            except Exception as e:
                logger.error(f"Webhook: Exception creating order for PaymentIntent {payment_intent_id}: {e}", exc_info=True)
                # Webhook still returns 200 - Stripe will retry if we return an error
        elif etype == "payment_intent.payment_failed":
            # Log payment failure - no order creation needed
            logger.info(f"Webhook: Payment failed for PaymentIntent {obj.get('id')}")
        else:
            logger.debug(f"Webhook: Unhandled event type {etype} for PaymentIntent {obj.get('id', 'unknown')}")

        return Response(status=200)

    @action(detail=True, methods=["post"], url_path="create-order")
    def create_order(self, request, pk=None):
        """
        Manually trigger order creation for a PaymentIntent.
        This is useful when webhook processing failed or was delayed.
        
        Route: POST /api/stripe/{intent_id}/create-order
        
        Purpose:
        - Validates stock availability for all order items
        - Creates order from PaymentIntent metadata
        - Updates inventory levels atomically  
        - Verifies user access to the PaymentIntent
        - Prevents duplicate order creation
        
        Returns:
        - Success: Order created confirmation with order ID
        - Error: Stock validation failures, access denied, or order creation errors
        """
        intent_id = pk
        
        try:
            payment_intent = stripe.PaymentIntent.retrieve(intent_id)
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve PaymentIntent {intent_id} for manual order creation: {e}", exc_info=True)
            return Response({"error": "Payment intent not found"}, status=400)
        
        # Verify the payment succeeded
        if payment_intent.get("status") != "succeeded":
            return Response(
                {"error": "PaymentIntent must be succeeded to create order"}, 
                status=400
            )
        
        # Check if order already exists
        metadata = payment_intent.get("metadata", {})
        existing_order_id = metadata.get("order_id")
        if existing_order_id:
            return Response(
                {"message": "Order already exists", "order_id": existing_order_id}, 
                status=200
            )
        
        # Verify user has access to this PaymentIntent
        user = getattr(request, "user", None)
        is_authed = bool(user and getattr(user, "is_authenticated", False))
        is_owner = False

        if is_authed and metadata.get("user_id") == str(user.id):
            is_owner = True
        else:
            gid = request.COOKIES.get(GUEST_COOKIE)
            if gid and gid == metadata.get("guest_id"):
                is_owner = True

        if not is_owner:
            return Response({"error": "forbidden"}, status=403)
        
        # Create the order
        try:
            order = OrderCreationService.create_order_from_payment_intent(payment_intent)
            if order:
                return Response({
                    "message": "Order created successfully",
                    "order_id": str(order.id)
                }, status=201)
            else:
                return Response(
                    {"error": "Failed to create order - check required fields"}, 
                    status=400
                )
        except Exception as e:
            logger.error(f"Exception creating order for PaymentIntent {intent_id}: {e}", exc_info=True)
            return Response(
                {"error": "Failed to create order"}, 
                status=500
            )
