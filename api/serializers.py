from rest_framework import serializers
from base.models import *

"""
Serializers for the corresponding models.
Converts model instances to and from JSON format for API interactions.
"""

class UserModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserModel
        fields = ["username", "name", "email", "password"]

class ProductModelSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(source="price.price", max_digits=10, decimal_places=2, read_only=True)
    class Meta:
        model = ProductModel
        fields = ["id", "name", "description", "images", "featured", "gender", "price"]

class CategoryModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryModel
        fields = ["id", "name", "description", "parentCategoryId"]