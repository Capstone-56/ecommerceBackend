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
    price = serializers.SerializerMethodField()
    class Meta:
        model = ProductModel
        fields = ["id", "name", "description", "images", "featured", "avg_rating", "price"]
    
    # append the price field to the serializer (lowest price of all items)
    def get_price(self, obj):
        items = obj.items.all()
        if items:
            return min(item.price for item in items if item.price is not None)
        return None

class CategoryModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryModel
        fields = ["internalName", "name", "description", "parentCategory"]