from rest_framework import viewsets, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

import logging

# Set up basic configuration for logging
logging.basicConfig(level=logging.DEBUG,  # Log messages with this level or higher
                    format='%(asctime)s - %(levelname)s - %(message)s')  # Format for log messages

from base.models import UserModel

from api.serializers import UserModelSerializer

class UserViewSet(viewsets.ViewSet):
    def list(self, request):
        """
        Retrieve all UserModel records.
        GET /api/user
        """
        users = UserModel.objects.all()
        serializer = UserModelSerializer(users, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """
        Retrieve a specific user by username.
        GET /api/user/{username}
        """
        user = get_object_or_404(UserModel, username=pk)
        serializer = UserModelSerializer(user)
        return Response(serializer.data)

    """
    def create(self, request):
        
        Create a new user.
        POST /api/user
        
        hashed = bcrypt.hashpw(request.data.get("password").encode(encoding="utf-8"), bcrypt.gensalt())
        request.data["password"] = hashed
        serializer = UserModelSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    """

    def update(self, request, pk=None):
        """
        Update an existing user.
        PUT /api/user/${id}
        """
        user = get_object_or_404(UserModel, pk=pk)
        serializer = UserModelSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        """
        Delete a specific user.
        DELETE /api/user/${id}
        """
        user = get_object_or_404(UserModel, pk=pk)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
