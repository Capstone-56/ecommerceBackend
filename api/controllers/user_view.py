from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404

import logging

# Set up basic configuration for logging
logging.basicConfig(level=logging.DEBUG,  # Log messages with this level or higher
                    format='%(asctime)s - %(levelname)s - %(message)s')  # Format for log messages

from base.enums.role import ROLE
from base.models import UserModel

from api.serializers import UserModelSerializer, PublicUserSerializer

class UserViewSet(viewsets.ViewSet):

    # for testing purposes, you need to be authenticated by attaching to request Headder:
    # Authorization: Bearer <accessToken>
    # to call GET /api/user
    def get_permissions(self):
        if self.action in ["list", "delete", "create"]:
            return [IsAuthenticated()]

        return [AllowAny()]

    def create(self, request):
        """
        Create a new user. Authorised only for admins.
        POST /api/user
        """
        if request.user.role != ROLE.ADMIN.value:
            return Response({'error': 'Permission denied. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = UserModelSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
        Retrieve a specific user by username, or 'me' for the current user.
        GET /api/user/{username} or /api/user/me
        """
        try:
            if pk == "me":
                user = request.user
                serializer = PublicUserSerializer(user)
                return Response(serializer.data)
            user = get_object_or_404(UserModel, username=pk)
            if request.user != user and request.user.role != ROLE.ADMIN.value:
                return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
            
            serializer = UserModelSerializer(user)
            return Response(serializer.data)
        except Exception as e:
            logging.error(f"Error in retrieve user: {str(e)}", exc_info=True)
            return Response({
                'error': 'An error occurred',
                'message': str(e),
                'type': type(e).__name__
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    def update(self, request, pk=None):
        """
        Update an existing user.
        PUT /api/user/${id}
        """
        user = get_object_or_404(UserModel, pk=pk)
        if request.user != user:
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = UserModelSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def destroy(self, request, pk=None):
        """
        TODO: Implement soft delete
        Delete a specific user. Authorized only for admins and users deleting their own accounts.
        DELETE /api/user/${id}
        """
        user = get_object_or_404(UserModel, pk=pk)

        if request.user != user and request.user.role != ROLE.ADMIN.value:
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        user.is_active = False
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
