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
    imageUrls = serializers.ListField(child=serializers.CharField(max_length=1000), required=False)
    variations = ProductConfigSerializer(many=True, required=False)
    product = serializers.SerializerMethodField()

    def get_product(self, obj):
        return ProductModelSerializer(obj.product).data

    class Meta:
        model = ProductItemModel
        fields = ["id", "product", "sku", "stock", "price", "imageUrls", "variations"]
    
class ProductModelSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()
    variations = serializers.SerializerMethodField()
    category = serializers.SlugRelatedField(slug_field='internalName', queryset=CategoryModel.objects.all())
    locations = serializers.SlugRelatedField(
        many=True,
        slug_field='country_code',
        queryset=LocationModel.objects.all()
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
            "category",
            "locations",
            "product_items",
            "variations"
        ]
    
    # Retrieve the price of an object based on the sorting context. If the sort is set to priceDesc, then the max_price is appended.
    def get_price(self, obj):
        sort = self.context.get("sort")
        if sort == "priceDesc":
            return getattr(obj, "maxPrice", None)
        elif sort =="priceAsc":
            # Default to min_price if priceAsc or no sort.
            return getattr(obj, "minPrice", None)
        
        # For product details it needs to be returned like this. Otherwise,
        # the price field won't be populated.
        return obj.items.values_list("price", flat=True).first()

    # Retrieve variations for the given product.
    def get_variations(self, obj):
        variants = VariantModel.objects.filter(
            productconfigmodel__productItem__product=obj
        ).select_related('variationType').distinct()

        grouped = defaultdict(list)
        for variant in variants:
            grouped[variant.variationType.name].append(variant.value)
        return grouped
    
    def create(self, validated_data):
        """
        Creates an entry into the product table, productItem table from the internal list of product information,
        and also productConfig table for the variations provided when creating a product e.g. "Blue", "M".
        """
        product_list_data = validated_data.pop("product_items")
        locations_data = validated_data.pop("locations", None)
        product = ProductModel.objects.create(**validated_data)

        if locations_data is not None:
            product.locations.set(locations_data)

        for internal_product_info in product_list_data:
            variations_data = internal_product_info.pop("variations")
            product_item = ProductItemModel.objects.create(product=product, **internal_product_info)
            for variant in variations_data:
                ProductConfigModel.objects.create(productItem=product_item, **variant)
        return product

    def update(self, instance, validated_data):
        """
        Updates a product with its associated product items and variant configurations.
        Handles creating new items, updating existing ones, and removing items not included.
        """
        product_items_data = validated_data.pop("product_items", None)
        locations_data = validated_data.pop('locations', None)

        # Update product-level fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if locations_data is not None:
            instance.locations.set(locations_data)
        
        # Handle product items updates
        if product_items_data is not None:
            # Get existing product items
            existing_items = {str(item.id): item for item in instance.items.all()}
            updated_item_ids = set()
            
            for item_data in product_items_data:
                variations_data = item_data.pop("variations", [])
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


class CartItemSerializer(serializers.ModelSerializer):
    productItem = ProductItemModelSerializer(read_only=True)
    quantity = serializers.IntegerField(min_value=1)

    # readonly, computed property that returns the total price of the item
    totalPrice = serializers.SerializerMethodField()

    class Meta:
        model = ShoppingCartItemModel
        fields = ["id", "productItem", "quantity", "totalPrice"]

    def get_totalPrice(self, obj):
        return obj.quantity * obj.productItem.price


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
            "id", "createdAt", "user", "guestUser", "address", "shippingVendor", 
            "totalPrice", "status", "items"
        ]
        read_only_fields = ["user", "guestUser"]


class ListOrderSerializer(serializers.ModelSerializer):
    """
    Simplified order serializer for list views - works for both user types
    """
    user = UserModelSerializer(read_only=True)
    guestUser = GuestUserSerializer(read_only=True)
    
    class Meta:
        model = OrderModel
        fields = [
            "id", "createdAt", "user", "guestUser", "address", "shippingVendor", 
            "totalPrice", "status"
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
    shippingVendorId = serializers.IntegerField(write_only=True)
    items = OrderItemSerializer(many=True, write_only=True)
    guestUser = GuestUserSerializer(read_only=True)
    
    class Meta:
        model = OrderModel
        fields = [
            "id", "createdAt", "addressId", "shippingVendorId", "totalPrice", "status",
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
        shipping_vendor_id = validated_data.pop("shippingVendorId")
        items_data = validated_data.pop("items")
        
        # Always create a new guest user for true anonymity
        guest_user = GuestUserModel.objects.create(**guest_data)
        
        try:
            address = AddressModel.objects.get(id=address_id)
            shipping_vendor = ShippingVendorModel.objects.get(id=shipping_vendor_id)
        except AddressModel.DoesNotExist:
            raise serializers.ValidationError(f"Address with id {address_id} does not exist")
        except ShippingVendorModel.DoesNotExist:
            raise serializers.ValidationError(f"ShippingVendor with id {shipping_vendor_id} does not exist")
        
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
            
            price = product_item.price  # Get price from ProductItemModel
            
            order_items.append({
                "productItem": product_item,
                "quantity": quantity,
                "price": price
            })
            total_price += price * quantity
        
        # Create order with calculated total price
        validated_data["totalPrice"] = total_price
        validated_data["address"] = address
        validated_data["shippingVendor"] = shipping_vendor
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
    shippingVendorId = serializers.IntegerField(write_only=True)
    user_id = serializers.UUIDField(write_only=True)
    items = OrderItemSerializer(many=True, write_only=True)
    user = UserModelSerializer(read_only=True)

    class Meta:
        model = OrderModel
        fields = [
            "id", "createdAt", "user", "user_id", "addressId", "shippingVendorId", 
            "totalPrice", "status", "items"
        ]
        read_only_fields = ["id", "createdAt", "totalPrice"]

    def create(self, validated_data):
        user_id = validated_data.pop("user_id")
        address_id = validated_data.pop("addressId")
        shipping_vendor_id = validated_data.pop("shippingVendorId")
        items_data = validated_data.pop("items")
        
        try:
            user = UserModel.objects.get(id=user_id)
            address = AddressModel.objects.get(id=address_id)
            shipping_vendor = ShippingVendorModel.objects.get(id=shipping_vendor_id)
        except UserModel.DoesNotExist:
            raise serializers.ValidationError(f"User with id {user_id} does not exist")
        except AddressModel.DoesNotExist:
            raise serializers.ValidationError(f"Address with id {address_id} does not exist")
        except ShippingVendorModel.DoesNotExist:
            raise serializers.ValidationError(f"ShippingVendor with id {shipping_vendor_id} does not exist")
        
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
            
            price = product_item.price  # Get price from ProductItemModel
            
            order_items.append({
                "productItem": product_item,
                "quantity": quantity,
                "price": price
            })
            total_price += price * quantity
        
        # Create order with calculated total price
        validated_data["totalPrice"] = total_price
        validated_data["address"] = address
        validated_data["shippingVendor"] = shipping_vendor
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
