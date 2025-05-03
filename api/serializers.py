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
    class Meta:
        model = ProductModel
        fields = ["id", "name", "description", "images", "featured", "avg_rating", "price"]
    
    # Retrieve the price of an object based on the sorting context. If the sort is set to priceDesc, then the max_price is appended.
    def get_price(self, obj):
        sort = self.context.get("sort")
        if sort == "priceDesc":
            return getattr(obj, "max_price", None)
        # Default to min_price if priceAsc or no sort.
        return getattr(obj, "min_price", None)


class CategoryModelSerializer(serializers.ModelSerializer):
    breadcrumb = serializers.SerializerMethodField()

    class Meta:
        model = CategoryModel
        fields = ["internalName", "name", "description", "parentCategory", "breadcrumb"]

    def get_breadcrumb(self, obj):
        # MPTTModel provides get_ancestors()
        return [
            {"name": anc.name, "internal_name": anc.internalName}
            for anc in obj.get_ancestors(include_self=True)
        ]