from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from api.serializers import UserModelSerializer
from base.models import *
from django.contrib.auth import logout

class AuthenticationViewSet(viewsets.ViewSet):
    """
    Handles user authentication operations like sign-up, login, token refresh, 2FA, etc.
    """

    @action(detail=False, methods=["post"], url_path="signup", permission_classes=[AllowAny])
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

    @action(detail=False, methods=["post"], url_path="login", permission_classes=[AllowAny])
    def login(self, request):
        """
        Log in a user by username OR email.

        POST /auth/login
        Request body JSON:
        {
          "username": "string (username or email)",
          "password": "string"
        }
        """
        identifier = request.data.get("username", "")
        password = request.data.get("password", "")

        # Choose lookup on email vs username
        lookup = {"email": identifier} if "@" in identifier else {"username": identifier}

        try:
            user = UserModel.objects.get(**lookup)
        except UserModel.DoesNotExist:
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.check_password(password):
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            return Response({"detail": "Account disabled"}, status=status.HTTP_403_FORBIDDEN)

        # Issue JWTs
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        return Response({
            "message": "Login successful",
            "access": str(access),
            "refresh": str(refresh),
            "user": UserModelSerializer(user).data
        }, status=200)

    @action(detail=False, methods=["delete"], url_path="logout", permission_classes=[AllowAny], authentication_classes=[])
    def logout(self, request):
        """
        Invalidate a JWT session by blacklisting the provided refresh token.

        DELETE /auth/logout
        Body (JSON):
        {
          "refresh": "<refresh_token>"
        }
        """
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            RefreshToken(refresh_token).blacklist()
        except Exception:
            return Response(
                {"detail": "Invalid refresh token"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"message": "Logged out successfully"},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["post"], url_path="refresh")
    def refresh_token(self, request):
        """
        Refresh an expiring JWT.

        POST /auth/refresh
        Request body JSON:
        { "refresh": "<refresh_token>" }
        """
        from rest_framework_simplejwt.views import TokenRefreshView
        return TokenRefreshView.as_view()(request._request)
