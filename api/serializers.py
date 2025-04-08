from rest_framework import serializers
from base.models import *

class UserModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserModel
        fields = ["username", "name", "email", "password"]

class TestModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestModel
        fields = ["username", "name", "email", "password"]

