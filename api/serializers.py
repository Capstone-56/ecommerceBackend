from collections import defaultdict
from rest_framework import serializers
from base.models import *

"""
Serializers for the corresponding models.
Converts model instances to and from JSON format for API interactions.
"""

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = AddressModel
        fields = ["addressLine", "city", "postcode", "state", "country"]


class UserAddressSerializer(serializers.ModelSerializer):
    address = AddressSerializer(read_only=True)

    class Meta:
        model = UserAddressModel
        fields = ["id", "address", "isDefault"]


class UserModelSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    isActive = serializers.BooleanField(source="is_active", read_only=True)
    isStaff = serializers.BooleanField(source="is_staff", read_only=True)
    isSuperuser = serializers.BooleanField(source="is_superuser", read_only=True)
    addresses = UserAddressSerializer(
        many=True,
        read_only=True,
        source="user_addresses"  # must match the related_name on UserAddressModel.user
    )

    class Meta:
        model = UserModel
        fields = [
            "id", "username", "email", "firstName", "lastName", "addresses",
            "phone", "password", "role", "isActive", "isStaff", "isSuperuser"
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = UserModel(**validated_data)
        user.set_password(password)
        user.save()
        return user

class ProductConfigSerializer(serializers.ModelSerializer):
    variant = serializers.PrimaryKeyRelatedField(queryset=VariantModel.objects.all())

    class Meta:
        model = ProductConfigModel
        fields = ['variant']

class ProductItemModelSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False)
    variations = ProductConfigSerializer(many=True, required=False)
    product = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()  # Final price after discounts
    currency = serializers.SerializerMethodField()  # Currency code based on location
    location = serializers.CharField(required=False)

    def get_product(self, obj):
        return ProductModelSerializer(obj.product, context=self.context).data
    
    def get_price(self, obj):
        """
        Get price from ProductItemLocation (with discounts) or ProductLocation (base price).
        """
        country_code = self.context.get("country_code")
        
        if country_code:
            # First try to get item-specific price with discount
            try:
                item_location = ProductItemLocationModel.objects.get(
                    productItem=obj,
                    location__country_code=country_code
                )
                return item_location.final_price
            except ProductItemLocationModel.DoesNotExist:
                # Fall back to base product price for this location
                try:
                    product_location = ProductLocationModel.objects.get(
                        product=obj.product,
                        location__country_code=country_code
                    )
                    return product_location.price
                except ProductLocationModel.DoesNotExist:
                    pass
        
        # No location-specific price found
        return None
    
    def to_representation(self, instance):
        """
        Override to include the location when reading.
        """
        representation = super().to_representation(instance)
        try:
            item_location = ProductItemLocationModel.objects.get(productItem=instance)
            representation['location'] = item_location.location.country_code
        except ProductItemLocationModel.DoesNotExist:
            representation['location'] = None
        return representation         
    
    def get_currency(self, obj):
        """
        Get currency code from location.
        """
        country_code = self.context.get("country_code")
        
        if country_code:
            # Try item-specific location first
            try:
                item_location = ProductItemLocationModel.objects.get(
                    productItem=obj,
                    location__country_code=country_code
                )
                return item_location.currency_code
            except ProductItemLocationModel.DoesNotExist:
                # Fall back to product location
                try:
                    product_location = ProductLocationModel.objects.get(
                        product=obj.product,
                        location__country_code=country_code
                    )
                    return product_location.currency_code
                except ProductLocationModel.DoesNotExist:
                    pass
        
        # No location-specific data found
        return None
    
    def create(self, validated_data):
        """
        Creates product items and product configs. 
        """
        variations_data = validated_data.pop("variations", [])
        location_data = validated_data.pop("location", None)

        # Pull from request manually.
        product_id = self.context["request"].data.get("product")
        product_item = ProductItemModel.objects.create(
            **validated_data,
            # Assign manually.
            product_id=product_id
        )

        # Get the location.
        item_location = LocationModel.objects.get(country_code=location_data)
        # Create a item location.
        ProductItemLocationModel.objects.create(location=item_location, productItem=product_item, discount=0)

        for variation in variations_data:
            ProductConfigModel.objects.create(
                productItem=product_item,
                variant=variation["variant"]
            )

        return product_item

    class Meta:
        model = ProductItemModel
        fields = ["id", "product", "sku", "stock", "price", "currency", "variations", "location"]
    
class ProductModelSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()  # Currency code based on location
    name = serializers.CharField(required=False, allow_blank=False)  # Accept for write
    description = serializers.CharField(required=False, allow_blank=True)  # Accept for write
    variations = serializers.SerializerMethodField()
    category = serializers.SlugRelatedField(slug_field='internalName', queryset=CategoryModel.objects.all())
    location_pricing = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField()),
        write_only=True, 
        required=True,
        help_text="List of objects with country_code, price, and currency (e.g. [{\"country_code\": \"US\", \"price\": 29.99, \"currency\": \"USD\"}])"
    )
    
    product_items = ProductItemModelSerializer(many=True, write_only=True)

    class Meta:
        model = ProductModel
        fields = [
            "id",
            "name",
            "description",
            "images",
            "featured",
            "avgRating",
            "price",
            "currency",
            "category",
            "location_pricing",
            "product_items",
            "variations"
        ]
    
    def to_representation(self, instance):
        """Override to compute name/description/locations from ProductLocation for reads"""
        ret = super().to_representation(instance)
        country_code = self.context.get("country_code")
        
        # Get name from ProductLocation
        if country_code:
            try:
                product_location = ProductLocationModel.objects.get(
                    product=instance,
                    location__country_code=country_code
                )
                ret['name'] = product_location.name
                ret['description'] = product_location.description
            except ProductLocationModel.DoesNotExist:
                # Fallback to first location
                first_location = ProductLocationModel.objects.filter(product=instance).first()
                ret['name'] = first_location.name if first_location else "Unnamed Product"
                ret['description'] = first_location.description if first_location else ""
        else:
            # No country specified, use first location
            first_location = ProductLocationModel.objects.filter(product=instance).first()
            ret['name'] = first_location.name if first_location else "Unnamed Product"
            ret['description'] = first_location.description if first_location else ""
        
        # Include location_pricing in output
        locations_data = []
        for product_location in ProductLocationModel.objects.filter(product=instance):
            locations_data.append({
                "country_code": product_location.location.country_code,
                "price": product_location.price,
                "currency": product_location.currency_code
            })
        
        ret['location_pricing'] = locations_data
        
        return ret
    
    # Retrieve the price of an object based on the sorting context. If the sort is set to priceDesc, then the max_price is appended.
    def get_price(self, obj):
        """Get price from ProductLocation - supports sorting"""
        sort = self.context.get("sort")
        country_code = self.context.get("country_code")
        
        if sort == "priceDesc":
            return getattr(obj, "maxPrice", None)
        elif sort =="priceAsc":
            # Default to min_price if priceAsc or no sort.
            return getattr(obj, "minPrice", None)
        
        # Otherwise get price for specific location
        if country_code:
            try:
                product_location = ProductLocationModel.objects.get(
                    product=obj,
                    location__country_code=country_code
                )
                return product_location.price
            except ProductLocationModel.DoesNotExist:
                pass
        
        # No location-specific price found
        return None
    
    def get_currency(self, obj):
        """
        Get currency code from location.
        Uses country_code from context.
        """
        country_code = self.context.get("country_code")
        
        if country_code:
            try:
                product_location = ProductLocationModel.objects.get(
                    product=obj,
                    location__country_code=country_code
                )
                return product_location.currency_code
            except ProductLocationModel.DoesNotExist:
                pass
        
        # No location-specific data found
        return None

    # Retrieve variations for the given product.
    def get_variations(self, obj):
        variants = VariantModel.objects.filter(
            productconfigmodel__productItem__product=obj
        ).select_related('variationType').distinct()

        grouped = defaultdict(list)
        for variant in variants:
            grouped[variant.variationType.name].append(variant.value)
        return grouped
    
    def validate(self, data):
        """
        Validate that location_pricing is provided for create operations.
        """
        # Skip validation for partial updates (PATCH requests)
        if self.partial:
            return data
            
        if not data.get('location_pricing'):
            raise serializers.ValidationError({
                'location_pricing': ['This field is required.']
            })
        return data

    def create(self, validated_data):
        """
        Creates an entry into the product table, productItem table from the internal list of product information,
        and also productConfig table for the variations provided when creating a product e.g. "Blue", "M".
        
        Also creates ProductLocation entries for name/description/price per location.
        """
        from base.models import LocationModel, ProductLocationModel
        
        # Extract data that won't go directly into ProductModel
        product_list_data = validated_data.pop("product_items")
        location_pricing_data = validated_data.pop("location_pricing")
        
        # Extract name/description from validated_data (they don't belong in ProductModel anymore)
        product_name = validated_data.pop("name", "Unnamed Product")
        product_description = validated_data.pop("description", "")
        
        # Create the product (without name/description)
        product = ProductModel.objects.create(**validated_data)

        # Create ProductLocation entries for name/description/price per location
        for pricing_item in location_pricing_data:
            location_code = pricing_item.get("country_code", "").upper()
            if not location_code:
                continue
                
            try:
                price = float(pricing_item.get("price"))
                location = LocationModel.objects.get(country_code=location_code)
                ProductLocationModel.objects.create(
                    product=product,
                    location=location,
                    name=product_name,
                    description=product_description,
                    price=price
                )
            except (LocationModel.DoesNotExist, (ValueError, TypeError, KeyError)):
                # Skip invalid locations or prices
                continue

        # Create product items (without price - it's now in ProductLocation)
        for internal_product_info in product_list_data:
            variations_data = internal_product_info.pop("variations", [])
            # Remove price from product item data since it doesn't have that field anymore
            internal_product_info.pop("price", None)
            # Remove imageUrls too if present (that field was also removed)
            internal_product_info.pop("imageUrls", None)

            item_location_code = internal_product_info.pop("location", None)

            product_item = ProductItemModel.objects.create(product=product, **internal_product_info)
            item_location = LocationModel.objects.get(country_code=item_location_code)

            ProductItemLocationModel.objects.create(location=item_location, productItem=product_item, discount=0)
            
            for variant in variations_data:
                ProductConfigModel.objects.create(productItem=product_item, **variant)
                
        return product

    def update(self, instance, validated_data):
        """
        Updates a product with its associated product items and variant configurations.
        Handles creating new items, updating existing ones, and removing items not included.
        Also updates ProductLocation entries for name/description/price.
        """
        from base.models import LocationModel, ProductLocationModel
        
        product_items_data = validated_data.pop("product_items", None)
        location_pricing_data = validated_data.pop('location_pricing', None)
        
        # Extract name/description from validated_data (they don't belong in ProductModel)
        product_name = validated_data.pop("name", None)
        product_description = validated_data.pop("description", None)

        # Update product-level fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Handle location_pricing updates
        if location_pricing_data is not None:
            existing_locations = ProductLocationModel.objects.filter(product=instance)
            existing_codes = {pl.location.country_code for pl in existing_locations}
            new_codes = {item['country_code'].upper() for item in location_pricing_data}
            
            # Create pricing map
            pricing_map = {item['country_code'].upper(): item for item in location_pricing_data}
            
            # Update existing locations
            for product_location in existing_locations:
                code = product_location.location.country_code
                if code in new_codes:
                    pricing_data = pricing_map[code]
                    product_location.price = float(pricing_data.get('price', product_location.price))
                    if product_name:
                        product_location.name = product_name
                    if product_description:
                        product_location.description = product_description
                    product_location.save()
                else:
                    # Remove locations not in new list
                    product_location.delete()
            
            # Create new locations
            for code in (new_codes - existing_codes):
                try:
                    location = LocationModel.objects.get(country_code=code)
                    pricing_data = pricing_map[code]
                    
                    # Get defaults from existing location if name/description not provided
                    existing_pl = ProductLocationModel.objects.filter(product=instance).first()
                    
                    ProductLocationModel.objects.create(
                        product=instance,
                        location=location,
                        name=product_name or (existing_pl.name if existing_pl else "Unnamed Product"),
                        description=product_description or (existing_pl.description if existing_pl else ""),
                        price=float(pricing_data.get('price', 0.0))
                    )
                except LocationModel.DoesNotExist:
                    pass
        elif product_name or product_description:
            # Update all existing ProductLocation entries (name/description only)
            for product_location in ProductLocationModel.objects.filter(product=instance):
                if product_name:
                    product_location.name = product_name
                if product_description:
                    product_location.description = product_description
                product_location.save()
        
        # Handle product items updates
        if product_items_data is not None:
            # Get existing product items
            existing_items = {str(item.id): item for item in instance.items.all()}
            updated_item_ids = set()
            
            for item_data in product_items_data:
                variations_data = item_data.pop("variations", [])
                # Remove fields that don't belong in ProductItemModel anymore
                item_data.pop("price", None)
                item_data.pop("imageUrls", None)
                item_id = item_data.get("id")
                
                # Convert item_id to string for consistent lookup, handle None case
                item_id_str = str(item_id) if item_id is not None else None
                
                if item_id_str and item_id_str in existing_items:
                    # Update existing item
                    item = existing_items[item_id_str]
                    for attr, value in item_data.items():
                        if attr != "id":
                            setattr(item, attr, value)
                    item.save()
                    updated_item_ids.add(item_id_str)
                else:
                    # Create new item only if no valid ID provided
                    # Remove 'id' from item_data to prevent conflicts
                    item_data.pop('id', None)
                    item = ProductItemModel.objects.create(product=instance, **item_data)
                    updated_item_ids.add(str(item.id))
                
                # Handle variations for this item
                if variations_data:
                    # Remove existing configurations for this item
                    ProductConfigModel.objects.filter(productItem=item).delete()
                    # Create new configurations
                    for variant_data in variations_data:
                        ProductConfigModel.objects.create(productItem=item, **variant_data)
            
            # Remove items that weren't included in the update
            if not self.partial:
                items_to_remove = set(existing_items.keys()) - updated_item_ids
                if items_to_remove:
                    ProductItemModel.objects.filter(
                        id__in=[existing_items[item_id].id for item_id in items_to_remove]
                    ).delete()
        
        return instance
    
class CategoryModelSerializer(serializers.ModelSerializer):
    breadcrumb = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = CategoryModel
        fields = ["internalName", "name", "description", "parentCategory", "breadcrumb", "children"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        view = self.context.get("view", None)
        if getattr(view, "action", None) == "list":
            # remove breadcrumb, description & parentCategory entirely
            # this is to save the amount of data returned when called GET /api/category
            # if we don't exclude these fields, the trees when growing too large
            # can make this API call returns a huge chunk of data
            # and freezes the browser
            self.fields.pop("breadcrumb", None)
            self.fields.pop("description", None)
            self.fields.pop("parentCategory", None)

    def get_breadcrumb(self, obj):
        # MPTTModel provides get_ancestors()
        return [
            {"name": anc.name, "internalName": anc.internalName}
            for anc in obj.get_ancestors(include_self=True)
        ]

    def get_children(self, obj):
        # Recursively serialize children categories
        children = obj.__class__.objects.filter(parentCategory=obj.internalName)
        return CategoryModelSerializer(children, many=True, context=self.context).data


class FlatCategorySerializer(serializers.ModelSerializer):
    """Flat serializer for admin - returns all fields without nesting"""
    class Meta:
        model = CategoryModel
        fields = ["internalName", "name", "description", "parentCategory"]


class CartItemSerializer(serializers.ModelSerializer):
    productItem = ProductItemModelSerializer(read_only=True)
    quantity = serializers.IntegerField(min_value=1)

    # readonly, computed property that returns the total price of the item
    totalPrice = serializers.SerializerMethodField()

    class Meta:
        model = ShoppingCartItemModel
        fields = ["id", "productItem", "quantity", "totalPrice"]

    def get_totalPrice(self, obj):
        """Calculate total price using ProductLocation pricing"""
        country_code = self.context.get("country_code")
        
        if not country_code:
            raise serializers.ValidationError("Location is required for pricing calculation")
        
        # Try to get location-specific price with discount
        try:
            item_location = ProductItemLocationModel.objects.get(
                productItem=obj.productItem,
                location__country_code=country_code
            )
            return obj.quantity * item_location.final_price
        except ProductItemLocationModel.DoesNotExist:
            # Fallback to ProductLocation base price
            try:
                product_location = ProductLocationModel.objects.get(
                    product=obj.productItem.product,
                    location__country_code=country_code
                )
                return obj.quantity * product_location.price
            except ProductLocationModel.DoesNotExist:
                raise serializers.ValidationError(
                    f"Product not available in location: {country_code}"
                )


class ShippingVendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingVendorModel
        fields = ["id", "name", "logoUrl", "isActive"]

    
class OrderItemSerializer(serializers.ModelSerializer):
    productItemId = serializers.UUIDField(write_only=True)
    productItem = ProductItemModelSerializer(read_only=True)
    
    class Meta:
        model = OrderItemModel
        fields = ["id", "productItemId", "productItem", "quantity", "price"]
        read_only_fields = ["price", "productItem"]  # Price and productItem are handled by backend


class GuestUserSerializer(serializers.ModelSerializer):
    """
    Serializer for GuestUserModel
    """
    class Meta:
        model = GuestUserModel
        fields = ["id", "email", "firstName", "lastName", "phone"]
        read_only_fields = ["id"]


class OrderSerializer(serializers.ModelSerializer):
    """
    General order serializer that works for both authenticated and guest orders
    """
    user = UserModelSerializer(read_only=True)
    guestUser = GuestUserSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = OrderModel
        fields = [
            "id", "createdAt", "user", "guestUser", "address",
            "totalPrice", "status", "items"
        ]
        read_only_fields = ["user", "guestUser"]


class ListOrderSerializer(serializers.ModelSerializer):
    """
    Simplified order serializer for list views - works for both user types
    """
    user = UserModelSerializer(read_only=True)
    guestUser = GuestUserSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    address = AddressSerializer(read_only=True)
    
    class Meta:
        model = OrderModel
        fields = [
            "id", "createdAt", "user", "guestUser", "address",
            "totalPrice", "status", "items", "paymentIntentId"
        ]
        read_only_fields = ["user", "guestUser"]


class CreateGuestOrderSerializer(serializers.ModelSerializer):
    """
    Serializer for creating orders with anonymous guest users.
    Always creates a new guest user for each order to maintain anonymity.
    """
    email = serializers.EmailField(write_only=True)
    firstName = serializers.CharField(max_length=255, write_only=True)
    lastName = serializers.CharField(max_length=255, write_only=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, write_only=True)
    addressId = serializers.UUIDField(write_only=True)
    items = OrderItemSerializer(many=True, write_only=True)
    guestUser = GuestUserSerializer(read_only=True)
    
    class Meta:
        model = OrderModel
        fields = [
            "id", "createdAt", "addressId", "totalPrice", "status",
            "email", "firstName", "lastName", "phone",
            "items", "guestUser"
        ]
        read_only_fields = ["id", "createdAt", "totalPrice", "guestUser"]

    def create(self, validated_data):
        guest_data = {
            "email": validated_data.pop("email"),
            "firstName": validated_data.pop("firstName"),
            "lastName": validated_data.pop("lastName"),
            "phone": validated_data.pop("phone", ""),
        }
        address_id = validated_data.pop("addressId")
        items_data = validated_data.pop("items")
        
        # Get country_code from context
        country_code = self.context.get("country_code")
        if not country_code:
            raise serializers.ValidationError("Location is required for order creation")
        
        # Always create a new guest user for true anonymity
        guest_user = GuestUserModel.objects.create(**guest_data)
        
        try:
            address = AddressModel.objects.get(id=address_id)
        except AddressModel.DoesNotExist:
            raise serializers.ValidationError(f"Address with id {address_id} does not exist")
        
        # Calculate total price
        total_price = 0
        order_items = []
        
        for item_data in items_data:
            product_item_id = item_data["productItemId"]
            quantity = item_data["quantity"]
            
            # Fetch the ProductItem from database
            try:
                product_item = ProductItemModel.objects.get(id=product_item_id)
            except ProductItemModel.DoesNotExist:
                raise serializers.ValidationError(f"ProductItem with id {product_item_id} does not exist")
            
            # Get location-specific price with discount or base price
            try:
                item_location = ProductItemLocationModel.objects.get(
                    productItem=product_item,
                    location__country_code=country_code
                )
                price = item_location.final_price
            except ProductItemLocationModel.DoesNotExist:
                # Fallback to ProductLocation base price for the same location
                try:
                    product_location = ProductLocationModel.objects.get(
                        product=product_item.product,
                        location__country_code=country_code
                    )
                    price = product_location.price
                except ProductLocationModel.DoesNotExist:
                    raise serializers.ValidationError(
                        f"Product item {product_item_id} not available in location: {country_code}"
                    )
            
            order_items.append({
                "productItem": product_item,
                "quantity": quantity,
                "price": price
            })
            total_price += price * quantity
        
        # Create order with calculated total price
        validated_data["totalPrice"] = total_price
        validated_data["address"] = address
        order = OrderModel.objects.create(guestUser=guest_user, **validated_data)
        
        # Create order items with calculated prices
        for item_data in order_items:
            OrderItemModel.objects.create(order=order, **item_data)
        
        return order


class CreateAuthenticatedOrderSerializer(serializers.ModelSerializer):
    """
    Serializer for creating orders with authenticated users (existing functionality)
    """
    addressId = serializers.UUIDField(write_only=True)
    user_id = serializers.UUIDField(write_only=True)
    items = OrderItemSerializer(many=True, write_only=True)
    user = UserModelSerializer(read_only=True)

    class Meta:
        model = OrderModel
        fields = [
            "id", "createdAt", "user", "user_id", "addressId",
            "totalPrice", "status", "items"
        ]
        read_only_fields = ["id", "createdAt", "totalPrice"]

    def create(self, validated_data):
        user_id = validated_data.pop("user_id")
        address_id = validated_data.pop("addressId")
        items_data = validated_data.pop("items")
        
        # Get country_code from context
        country_code = self.context.get("country_code")
        if not country_code:
            raise serializers.ValidationError("Location is required for order creation")
        
        try:
            user = UserModel.objects.get(id=user_id)
            address = AddressModel.objects.get(id=address_id)
        except UserModel.DoesNotExist:
            raise serializers.ValidationError(f"User with id {user_id} does not exist")
        except AddressModel.DoesNotExist:
            raise serializers.ValidationError(f"Address with id {address_id} does not exist")
        
        # Calculate total price
        total_price = 0
        order_items = []
        
        for item_data in items_data:
            product_item_id = item_data["productItemId"]
            quantity = item_data["quantity"]
            
            # Fetch the ProductItem from database
            try:
                product_item = ProductItemModel.objects.get(id=product_item_id)
            except ProductItemModel.DoesNotExist:
                raise serializers.ValidationError(f"ProductItem with id {product_item_id} does not exist")
            
            # Get location-specific price with discount or base price
            try:
                item_location = ProductItemLocationModel.objects.get(
                    productItem=product_item,
                    location__country_code=country_code
                )
                price = item_location.final_price
            except ProductItemLocationModel.DoesNotExist:
                # Fallback to ProductLocation base price for the same location
                try:
                    product_location = ProductLocationModel.objects.get(
                        product=product_item.product,
                        location__country_code=country_code
                    )
                    price = product_location.price
                except ProductLocationModel.DoesNotExist:
                    raise serializers.ValidationError(
                        f"Product item {product_item_id} not available in location: {country_code}"
                    )
            
            order_items.append({
                "productItem": product_item,
                "quantity": quantity,
                "price": price
            })
            total_price += price * quantity
        
        # Create order with calculated total price
        validated_data["totalPrice"] = total_price
        validated_data["address"] = address
        validated_data["user"] = user
        order = OrderModel.objects.create(**validated_data)
        
        # Create order items with calculated prices
        for item_data in order_items:
            OrderItemModel.objects.create(order=order, **item_data)
        
        return order
    
class VariationTypeSerializer(serializers.ModelSerializer):
    variant_values = serializers.SerializerMethodField()

    class Meta:
        model = VariationTypeModel
        fields = ["id", "name", "category", "variant_values"]

    def get_variant_values(self, obj):
        variations = VariantModel.objects.filter(variationType=obj)

        return [
            {"value": variant.value, "id": variant.id}
            for variant in variations
        ]

class LocationSerializer(serializers.ModelSerializer):

    class Meta:
        model = LocationModel
        fields = ["country_code", "country_name", "currency_code"]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make country_code read-only for updates (when instance exists)
        if self.instance is not None:
            self.fields["country_code"].read_only = True 
