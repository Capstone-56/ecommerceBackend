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
    class Meta:
        model = ProductModel
        fields = ["id", "name", "description", "images"]


class CategoryModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryModel
        fields = ["id", "name", "description", "parentCategory"]
