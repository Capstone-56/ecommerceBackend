import json
import logging
import stripe
from decimal import Decimal
from django.db import transaction
from django.db.models import F
from base.models import OrderModel, UserModel, ShoppingCartItemModel, ProductItemModel
from base.enums import ORDER_STATUS
from api.serializers import CreateGuestOrderSerializer, CreateAuthenticatedOrderSerializer
from .address_service import AddressService

logger = logging.getLogger(__name__)


class OrderCreationService:
    """Service for creating orders PaymentIntent data."""
    
    @staticmethod
    def create_order_from_payment_intent(payment_intent):
        """
        Creates an order from a successful Stripe PaymentIntent.
        
        Args:
            payment_intent (dict): Stripe PaymentIntent object
            
        Returns:
            OrderModel: Created order instance, or None if failed
        """
        metadata = payment_intent.get("metadata", {})
        
        # Extract basic data
        user_id = metadata.get("user_id")
        is_authenticated = metadata.get("is_authenticated", "False") == "True"
        
        # authenticated users: from db. guests: from metadata
        if is_authenticated and user_id:
            # Get cart items from db
            try:
                from base.models import ShoppingCartItemModel
                cart_db_items = ShoppingCartItemModel.objects.filter(user_id=user_id).select_related('productItem')
                cart_items = [
                    {"product_item_id": str(item.productItem.id), "qty": item.quantity}
                    for item in cart_db_items
                ]
                
                if not cart_items:
                    logger.error(f"No cart items found in database for authenticated user {user_id}")
                    return None
                    
            except Exception as e:
                logger.error(f"Failed to retrieve cart from database for user {user_id}: {e}")
                return None
        else:
            # Get cart items from metadata
            cart_items_str = metadata.get("cart_items")
            if not cart_items_str:
                logger.error(f"No cart_items in metadata for guest PaymentIntent {payment_intent.get('id')}")
                return None
                
            try:
                cart_items_raw = json.loads(cart_items_str)
                # Handle both formats: full and compressed
                cart_items = []
                for item in cart_items_raw:
                    if "product_item_id" in item:
                        cart_items.append({"product_item_id": item["product_item_id"], "qty": item["qty"]})
                    else:
                        cart_items.append({"product_item_id": item["id"], "qty": item["q"]})
                        
            except json.JSONDecodeError as e:
                logger.error(f"Invalid cart_items JSON in PaymentIntent {payment_intent.get('id')}: {e}")
                return None
        
        # Extract required order fields
        address_id = metadata.get("address_id")
        shipping_vendor_id = metadata.get("shipping_vendor_id")
        
        if not shipping_vendor_id:
            logger.error(f"Missing required shipping vendor ID for PaymentIntent {payment_intent.get('id')}")
            return None
        
        try:
            payment_intent_id = payment_intent.get("id")
            
            # Check for duplicate order
            existing_order = OrderModel.objects.filter(paymentIntentId=payment_intent_id).first()
            if existing_order:
                logger.info(f"Order {existing_order.id} already exists for PaymentIntent {payment_intent_id}")
                return existing_order
            
            with transaction.atomic():
                # Create address from shipping data if needed
                if not address_id:
                    address_id = AddressService.create_from_shipping_metadata(metadata)
                    if not address_id:
                        raise ValueError("Failed to create address from shipping metadata")
                
                # Prepare order data based on user type
                if is_authenticated and user_id:
                    order_data = OrderCreationService._prepare_authenticated_order_data(
                        user_id, address_id, shipping_vendor_id, cart_items
                    )
                    serializer = CreateAuthenticatedOrderSerializer(data=order_data)
                else:
                    order_data = OrderCreationService._prepare_guest_order_data(
                        metadata, address_id, shipping_vendor_id, cart_items
                    )
                    if not order_data:
                        raise ValueError("Failed to prepare guest order data")
                    serializer = CreateGuestOrderSerializer(data=order_data)
                
                if not serializer.is_valid():
                    raise ValueError(f"Order serializer validation failed: {serializer.errors}")
                
                # Validate and update stock before creating order
                stock_validation_result = OrderCreationService._validate_and_update_stock(cart_items)
                if not stock_validation_result["success"]:
                    raise ValueError(f"Stock validation failed: {stock_validation_result['error']}")
                
                # Create the order
                order = serializer.save()
                
                # Log amounts for monitoring
                payment_amount = Decimal(str(payment_intent.get("amount", 0))) / Decimal('100')
                logger.info(f"Order {order.id} created: PaymentIntent=${payment_amount}, Order=${order.totalPrice}")
                
                # Update order status and PaymentIntent ID
                order.status = ORDER_STATUS.PROCESSING.value
                order.paymentIntentId = payment_intent_id
                order.save()
                
                # Clear authenticated user's cart after successful order creation
                if is_authenticated and user_id:
                    OrderCreationService._clear_user_cart(user_id)
                
            # Update PaymentIntent metadata outside transaction
            OrderCreationService._update_payment_intent_metadata(payment_intent_id, order.id, payment_intent)
            
            logger.info(f"Successfully created order {order.id} for PaymentIntent {payment_intent_id}")
            return order
                
        except Exception as e:
            logger.error(f"Failed to create order for PaymentIntent {payment_intent.get('id')}: {e}", exc_info=True)
            return None
    
    @staticmethod
    def _prepare_authenticated_order_data(user_id, address_id, shipping_vendor_id, cart_items):
        return {
            "user_id": user_id,
            "addressId": address_id,
            "shippingVendorId": int(shipping_vendor_id),
            "items": [{"productItemId": item["product_item_id"], "quantity": item["qty"]} for item in cart_items]
        }
    
    @staticmethod
    def _prepare_guest_order_data(metadata, address_id, shipping_vendor_id, cart_items):
        guest_email = metadata.get("guest_email")
        guest_first_name = metadata.get("guest_first_name", "")
        guest_last_name = metadata.get("guest_last_name", "")
        guest_phone = metadata.get("shipping_phone", "")
        
        if not guest_email:
            logger.error("Missing guest email for guest order creation")
            return None
        
        return {
            "email": guest_email,
            "firstName": guest_first_name,
            "lastName": guest_last_name,
            "phone": guest_phone,
            "addressId": address_id,
            "shippingVendorId": int(shipping_vendor_id),
            "items": [{"productItemId": item["product_item_id"], "quantity": item["qty"]} for item in cart_items]
        }
    
    @staticmethod
    def _clear_user_cart(user_id):
        """Clear authenticated user's cart after successful order creation."""
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
            # Don't fail the transaction, order was created successfully
        except Exception as e:
            logger.error(f"Failed to clear cart for user {user_id} after order creation: {e}", exc_info=True)
            # Don't fail the transaction for cart clearing issues, order creation succeeded
    
    @staticmethod
    def _update_payment_intent_metadata(payment_intent_id, order_id, payment_intent):
        """Update PaymentIntent metadata with order ID."""
        try:
            stripe.PaymentIntent.modify(
                payment_intent_id,
                metadata={
                    **payment_intent.get("metadata", {}),
                    "order_id": str(order_id)
                }
            )
            logger.debug(f"Updated PaymentIntent {payment_intent_id} metadata with order ID {order_id}")
        except Exception as e:
            logger.warning(f"Failed to update PaymentIntent {payment_intent_id} with order ID {order_id}: {e}")
            # doesn't affect order creation success
    
    @staticmethod
    def _validate_and_update_stock(cart_items):
        """
        Validates stock availability and updates stock levels atomically.
        
        Args:
            cart_items: List of cart items with product_item_id and qty
            
        Returns:
            dict: {"success": bool, "error": str or None}
        """
        try:
            insufficient_stock_items = []
            
            # Get all product items with current stock levels
            product_item_ids = [item["product_item_id"] for item in cart_items]
            product_items = ProductItemModel.objects.select_for_update().filter(
                id__in=product_item_ids
            ).select_related('product')
            
            # Create mapping for quick lookup
            product_items_dict = {str(item.id): item for item in product_items}
            
            # Validate stock availability
            for cart_item in cart_items:
                product_item_id = cart_item["product_item_id"]
                requested_qty = cart_item["qty"]
                
                product_item = product_items_dict.get(product_item_id)
                if not product_item:
                    insufficient_stock_items.append({
                        "productItemId": product_item_id,
                        "error": "Product not found"
                    })
                    continue
                
                if product_item.stock < requested_qty:
                    insufficient_stock_items.append({
                        "productItemId": product_item_id,
                        "requested": requested_qty,
                        "available": product_item.stock,
                        "name": product_item.product.name
                    })
            
            if insufficient_stock_items:
                return {
                    "success": False,
                    "error": f"Insufficient stock for items: {insufficient_stock_items}"
                }
            
            # Update stock levels atomically
            for cart_item in cart_items:
                product_item_id = cart_item["product_item_id"]
                requested_qty = cart_item["qty"]
                
                # Use F() expression for atomic updates to prevent race conditions
                ProductItemModel.objects.filter(id=product_item_id).update(
                    stock=F('stock') - requested_qty
                )
            
            logger.info(f"Successfully updated stock for {len(cart_items)} items")
            return {"success": True, "error": None}
            
        except Exception as e:
            logger.error(f"Stock validation/update failed: {e}", exc_info=True)
            return {"success": False, "error": f"Stock update failed: {str(e)}"}