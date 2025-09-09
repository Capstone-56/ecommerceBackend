from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple
import uuid
import json
import stripe
import logging

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import transaction

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from base.models import ProductItemModel, ShoppingCartItemModel, UserModel, OrderModel
from base.enums import ORDER_STATUS
from api.serializers import CreateGuestOrderSerializer, CreateAuthenticatedOrderSerializer, AddressSerializer

stripe.api_key = settings.STRIPE_SECRET_KEY

GUEST_COOKIE = "guest_id"
GUEST_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

# Set up logger for this module
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
        - Fetches current product prices from database
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
        - Error: Validation errors for empty cart, missing products, or Stripe errors
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

        # Get pricing and names from ProductItem IDs directly
        price_by_product_item: dict[str, Decimal] = {}
        name_by_product_item: dict[str, str] = {}

        # Query ProductItems directly by their IDs
        product_items = ProductItemModel.objects.filter(id__in=product_item_ids).select_related('product')
        for item in product_items:
            price_by_product_item[str(item.id)] = Decimal(str(item.price))
            name_by_product_item[str(item.id)] = item.product.name or "Product"

        # Sum + prepare summary
        missing_product_items: list[str] = []
        total = Decimal("0")
        items_summary: list[dict] = []

        for nl in lines_norm:
            product_item_id, qty = nl["product_item_id"], nl["qty"]
            unit = price_by_product_item.get(product_item_id, Decimal("0"))
            if unit <= 0:
                missing_product_items.append(product_item_id)
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
        cart_items_str = json.dumps([{"product_item_id": nl["product_item_id"], "qty": nl["qty"]} for nl in lines_norm])
        
        metadata = {
            "user_id": str(user.id) if is_authed else "",
            "guest_id": guest_id if not is_authed else "",
            "cart_items": cart_items_str,
            "total_price": str(float(total)),
            "is_authenticated": str(is_authed),
        }
        
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
                    samesite="Lax",
                    secure=False,  # change to True on HTTPS
                )
            return resp
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=400)

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
            updated_metadata.update({
                "guest_email": guest_email,
                "guest_first_name": guest_first_name or name.split()[0] if name else "",
                "guest_last_name": guest_last_name or name.split()[-1] if name and len(name.split()) > 1 else "",
            })
        
        # Update the PaymentIntent with new metadata
        try:
            stripe.PaymentIntent.modify(intent_id, metadata=updated_metadata)
        except stripe.error.StripeError as e:
            return Response({"error": f"Failed to update payment intent: {str(e)}"}, status=400)

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
        - Creates orders from PaymentIntent metadata for both authenticated and guest users
        - Updates order status to PROCESSING and stores order ID in PaymentIntent metadata

        Webhook Events Handled:
        - payment_intent.succeeded: Creates order and clears user cart
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
                order = self._create_order_from_payment_intent(obj)
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
        """
        intent_id = pk
        
        try:
            payment_intent = stripe.PaymentIntent.retrieve(intent_id)
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=400)
        
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
            order = self._create_order_from_payment_intent(payment_intent)
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
            return Response(
                {"error": f"Error creating order: {str(e)}"}, 
                status=500
            )
    
    def create_address_from_shipping_metadata(self, metadata):
        """
        Creates an address from shipping metadata stored in PaymentIntent.
        """
        try:
            # Combine line1 and line2 for full address
            line1 = metadata.get("shipping_line1", "")
            line2 = metadata.get("shipping_line2", "")
            
            if line2:
                full_address = f"{line2}, {line1}"  # Unit/Apt first, then street
            else:
                full_address = line1
            
            address_data = {
                "addressLine": full_address,
                "city": metadata.get("shipping_city", ""),
                "postcode": metadata.get("shipping_postal_code", ""),
                "state": metadata.get("shipping_state", ""),
                "country": metadata.get("shipping_country", ""),
            }
            
            serializer = AddressSerializer(data=address_data)
            if serializer.is_valid():
                address = serializer.save()
                logger.debug(f"Created address {address.id} from shipping metadata")
                return str(address.id)
            else:
                logger.error(f"Address creation validation failed: {serializer.errors}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create address from shipping metadata: {e}", exc_info=True)
            return None
    
    def _create_order_from_payment_intent(self, payment_intent):
        """
        Creates an order from a successful Stripe PaymentIntent.
        """
        metadata = payment_intent.get("metadata", {})
        
        # Extract basic data
        user_id = metadata.get("user_id")
        is_authenticated = metadata.get("is_authenticated", "False") == "True"
        
        # Extract cart items
        cart_items_str = metadata.get("cart_items")
            
        try:
            cart_items = json.loads(cart_items_str)
        except json.JSONDecodeError:
            return None
        
        # Extract required order fields
        address_id = metadata.get("address_id")
        shipping_vendor_id = metadata.get("shipping_vendor_id")
        
        if not shipping_vendor_id:
            logger.error(f"Missing required shipping vendor ID for PaymentIntent {payment_intent.get('id')}")
            return None
        
        try:
            payment_intent_id = payment_intent.get("id")
            
            # Check for duplicate order (prevent webhook retries from creating multiple orders)
            existing_order = OrderModel.objects.filter(paymentIntentId=payment_intent_id).first()
            if existing_order:
                logger.info(f"Order {existing_order.id} already exists for PaymentIntent {payment_intent_id}")
                return existing_order
            
            with transaction.atomic():
                # Create address from shipping data if needed (part of transaction)
                if not address_id:
                    address_id = self.create_address_from_shipping_metadata(metadata)
                    if not address_id:
                        raise ValueError("Failed to create address from shipping metadata")
                
                if is_authenticated and user_id:
                    # Create authenticated user order
                    order_data = {
                        "user_id": user_id,
                        "addressId": address_id,
                        "shippingVendorId": int(shipping_vendor_id),
                        "items": [{"productItemId": item["product_item_id"], "quantity": item["qty"]} for item in cart_items]
                    }
                    serializer = CreateAuthenticatedOrderSerializer(data=order_data)
                else:
                    # Create guest user order
                    guest_email = metadata.get("guest_email")
                    guest_first_name = metadata.get("guest_first_name", "")
                    guest_last_name = metadata.get("guest_last_name", "")
                    guest_phone = metadata.get("shipping_phone", "")
                    
                    if not guest_email:
                        raise ValueError("Missing guest email for guest order creation")
                    
                    order_data = {
                        "email": guest_email,
                        "firstName": guest_first_name,
                        "lastName": guest_last_name,
                        "phone": guest_phone,
                        "addressId": address_id,
                        "shippingVendorId": int(shipping_vendor_id),
                        "items": [{"productItemId": item["product_item_id"], "quantity": item["qty"]} for item in cart_items]
                    }
                    serializer = CreateGuestOrderSerializer(data=order_data)
                
                if not serializer.is_valid():
                    raise ValueError(f"Order serializer validation failed: {serializer.errors}")
                
                # Create the order
                order = serializer.save()
                
                # Validate order total matches PaymentIntent amount
                payment_amount_cents = payment_intent.get("amount", 0)
                payment_amount_dollars = Decimal(str(payment_amount_cents)) / Decimal('100')
                order_total_dollars = Decimal(str(order.totalPrice))
                
                # Allow small rounding differences (1 cent tolerance)
                amount_difference = abs(payment_amount_dollars - order_total_dollars)
                if amount_difference > Decimal('0.01'):
                    logger.error(
                        f"Order total mismatch for PaymentIntent {payment_intent_id}: "
                        f"PaymentIntent=${payment_amount_dollars}, Order=${order_total_dollars}, "
                        f"Difference=${amount_difference}"
                    )
                    raise ValueError(
                        f"Order total ${order_total_dollars} does not match PaymentIntent amount ${payment_amount_dollars}"
                    )
                
                logger.debug(f"Order total validation passed: ${order_total_dollars} matches PaymentIntent amount")
                
                # Update order status to PROCESSING since payment succeeded
                order.status = ORDER_STATUS.PROCESSING.value
                # Store PaymentIntent ID for reliable lookup
                order.paymentIntentId = payment_intent.get("id")
                order.save()
                
                # Clear authenticated user's cart after successful order creation
                if is_authenticated and user_id:
                    try:
                        user = UserModel.objects.get(id=user_id)
                        cart_items_count = ShoppingCartItemModel.objects.filter(user=user).count()
                        if cart_items_count > 0:
                            deleted_count = ShoppingCartItemModel.objects.filter(user=user).delete()[0]
                            logger.info(f"Cleared {deleted_count} cart items for user {user_id} after order creation")
                        else:
                            logger.debug(f"No cart items to clear for user {user_id}")
                    except UserModel.DoesNotExist:
                        logger.warning(f"User {user_id} not found when trying to clear cart after order creation")
                        # Don't fail the transaction - order was created successfully
                    except Exception as e:
                        logger.error(f"Failed to clear cart for user {user_id} after order creation: {e}", exc_info=True)
                        # Don't fail the transaction for cart clearing issues - order creation succeeded
                
            # Update PaymentIntent metadata outside transaction
            try:
                stripe.PaymentIntent.modify(
                    payment_intent_id,
                    metadata={
                        **payment_intent.get("metadata", {}),
                        "order_id": str(order.id)
                    }
                )
                logger.debug(f"Updated PaymentIntent {payment_intent_id} metadata with order ID {order.id}")
            except Exception as e:
                logger.warning(f"Failed to update PaymentIntent {payment_intent_id} with order ID {order.id}: {e}")
                # This doesn't affect order creation success
            
            logger.info(f"Successfully created order {order.id} for PaymentIntent {payment_intent_id}")
            return order
                
        except Exception as e:
            logger.error(f"Failed to create order for PaymentIntent {payment_intent.get('id')}: {e}", exc_info=True)
            return None