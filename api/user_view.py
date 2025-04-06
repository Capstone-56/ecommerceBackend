from rest_framework import viewsets, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from base.models import *

from .serializers import UserModelSerializer

class UserViewSet(viewsets.ViewSet):
    def list(self, request):
        # Retrieve all UserModel records from the database
        users = UserModel.objects.all()
        serializer = UserModelSerializer(users, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        # Retrieve a specific user or return a 404 if not found
        user = get_object_or_404(UserModel, pk=pk)
        serializer = UserModelSerializer(user)
        return Response(serializer.data)

    def update(self, request, pk=None):
        # Retrieve the user, update with provided data, and validate
        user = get_object_or_404(UserModel, pk=pk)
        serializer = UserModelSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
