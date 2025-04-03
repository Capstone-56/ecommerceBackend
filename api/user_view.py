from rest_framework import viewsets
from rest_framework.response import Response

from .serializers import UserModelSerializer

from base.models import *

class UserViewSet(viewsets.ViewSet):
    def list(self, request):
        fake_users = [
            UserModel(id="0", name="Dan"),
            UserModel(id="1", name="Ngo")
        ]
        serializer = UserModelSerializer(fake_users, many=True)

        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        # Create a fake user based on the provided pk
        fake_user = UserModel(id=pk, name="Hello")
        serializer = UserModelSerializer(fake_user)

        return Response(serializer.data)

    def update(self, request, pk=None):
        data = request.data
        # Simulate an updated user instance using the data received.
        # In a real implementation, you would query the database and update the record.
        fake_updated_user = UserModel(id=pk, name=data.get("name", "Default Name"))
        serializer = UserModelSerializer(fake_updated_user)

        return Response(serializer.data)
