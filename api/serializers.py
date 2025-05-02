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