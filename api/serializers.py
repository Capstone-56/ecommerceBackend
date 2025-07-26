from collections import defaultdict
from rest_framework import serializers
from base.models import *

"""
Serializers for the corresponding models.
Converts model instances to and from JSON format for API interactions.
"""

class AddressBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = AddressBookModel
        fields = ["addressLine", "city", "postcode", "state", "country"]


class UserAddressSerializer(serializers.ModelSerializer):
    address = AddressBookSerializer(read_only=True)

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


class ProductModelSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()
    variations = serializers.SerializerMethodField()
    class Meta:
        model = ProductModel
        fields = ["id", "name", "description", "images", "featured", "avgRating", "price", "variations"]
    
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
    
class ProductItemModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductItemModel
        fields = ["id", "product", "sku", "stock", "price", "imageUrls"]


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
    productItem = ProductModelSerializer(source="productItem.product", read_only=True)
    quantity = serializers.IntegerField(min_value=1)

    # readonly, auto-calculated field that returns the total price of the item
    totalPrice = serializers.SerializerMethodField()

    class Meta:
        model = ShoppingCartItemModel
        fields = ["id", "productItem", "quantity", "totalPrice"]

    def get_totalPrice(self, obj):
        return obj.quantity * obj.productItem.price
