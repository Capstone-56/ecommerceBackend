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
    class Meta:
        model = ProductModel
        fields = ["id", "name", "description", "images"]

class CategoryModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryModel
        fields = ["id", "name", "description", "parentCategoryId"]