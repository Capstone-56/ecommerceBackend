from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from api.serializers import UserModelSerializer

class AuthenticationViewSet(viewsets.ViewSet):
    """
    Handles user authentication operations like sign-up, login, 2FA, etc.
    """

    @action(detail=False, methods=["post"], url_path="signup")
    def signup(self, request):
        """
        Register a new user.
        POST /auth/signup
        Body:
        {
            "username": string,
            "email": string,
            "firstName": string,
            "lastName": string,
            "phone": string,
            "password": string,
            "role": string (correspond to the "role" enum)
        }
        """
        serializer = UserModelSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "message": "User registered successfully",
                "user_id": user.id,
                "email": user.email
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
