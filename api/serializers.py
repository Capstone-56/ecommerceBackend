from rest_framework import serializers
from base.models import *

class UserModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserModel
        fields = ["username", "name", "email", "password"]

class ProductModelSerializer(serializers.ModelSerializer):
    """
    Serializer for the ProductModel.
    Converts ProductModel instances to and from JSON format for API interactions.
    """
    class Meta:
        model = ProductModel
        fields = ["NAME", "DESCRIPTION", "IMAGES"]
