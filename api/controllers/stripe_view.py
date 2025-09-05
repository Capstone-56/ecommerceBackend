from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple
import uuid
import json
import stripe

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from base.models import ProductItemModel
from base.enums import ORDER_STATUS
from api.serializers import CreateGuestOrderSerializer, CreateAuthenticatedOrderSerializer, AddressSerializer

stripe.api_key = settings.STRIPE_SECRET_KEY

GUEST_COOKIE = "guest_id"
GUEST_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

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
        - Processes payment success/failure notifications
        - Updates order status based on payment events
        - Provides secure communication between Stripe and the application
        
        Authentication:
        - Uses Stripe signature verification instead of Django auth
        - CSRF exempt as Stripe doesn't send CSRF tokens

        Returns:
        - 200 OK: Event processed successfully
        - 400 Bad Request: Invalid signature or malformed payload

        Note: Has TODOs to implement order handling
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
            try:
                order = self._create_order_from_payment_intent(obj)
                if order:
                    print(f"Order {order.id} created successfully for PaymentIntent {obj.get('id')}")
                else:
                    print(f"Failed to create order for PaymentIntent {obj.get('id')} - insufficient data")
            except Exception as e:
                print(f"Error creating order for PaymentIntent {obj.get('id')}: {e}")
                import traceback
                traceback.print_exc()
        elif etype == "payment_intent.payment_failed":
            # Log payment failure - no order creation needed
            print(f"Payment failed for PaymentIntent {obj.get('id')}")
        else:
            print(f"Unhandled webhook event type: {etype}")

        return Response(status=200)
    
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
                return str(address.id)
            else:
                print(f"Address creation failed: {serializer.errors}")
                return None
                
        except Exception as e:
            print(f"Error creating address from shipping metadata: {e}")
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
        
        # Create address from shipping data if not provided
        if not address_id:
            address_id = self.create_address_from_shipping_metadata(metadata)
            if not address_id:
                print("Failed to create address from shipping metadata")
                return None
        
        if not shipping_vendor_id:
            print(f"Missing required shipping vendor ID: shipping_vendor_id={shipping_vendor_id}")
            return None
        
        try:
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
                    print("Missing guest email for guest order creation")
                    return None
                
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
            
            if serializer.is_valid():
                order = serializer.save()
                # Update order status to PROCESSING since payment succeeded
                order.status = ORDER_STATUS.PROCESSING.value
                order.save()
                
                # Store order ID back in PaymentIntent metadata for easier lookup
                try:
                    stripe.PaymentIntent.modify(
                        payment_intent.get("id"),
                        metadata={
                            **payment_intent.get("metadata", {}),
                            "order_id": str(order.id)
                        }
                    )
                except Exception as e:
                    print(f"Failed to update PaymentIntent with order ID: {e}")
                
                return order
            else:
                print(f"Order serializer validation failed: {serializer.errors}")
                return None
                
        except Exception as e:
            print(f"Exception creating order: {e}")
            return None