from rest_framework import serializers
from base.models import *

"""
Serializers for the corresponding models.
Converts model instances to and from JSON format for API interactions.
"""

class UserModelSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = UserModel
        fields = [
            "id", "username", "email", "firstName", "lastName",
            "phone", "address", "city", "postcode", "state", "country",
            "password", "role"
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
        fields = ["id", "name", "description", "parentCategoryId"]