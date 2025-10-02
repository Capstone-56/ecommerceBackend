from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from api.serializers import UserModelSerializer
from base import Constants
from base import utils
from base.enums import ROLE
from base.models import *

class AuthenticationViewSet(viewsets.ViewSet):
    """
    Handles user authentication operations like sign-up, login, token refresh, 2FA, etc.
    """

    @action(detail=False, methods=["post"], permission_classes=[AllowAny], url_path="signup", authentication_classes=[])
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
        request.data["role"] = ROLE.CUSTOMER
        serializer = UserModelSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            refreshToken = RefreshToken.for_user(user)
            accessToken = refreshToken.access_token
            utils.store_hashed_refresh(user, str(refreshToken))

            return setCookie(accessToken, refreshToken, user.role, user.id)

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

        user = UserModel.objects.filter(**lookup).first()
        if not user or not user.check_password(password):
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            return Response({"detail": "Account disabled"}, status=status.HTTP_403_FORBIDDEN)

        # Issue JWTs
        refreshToken = RefreshToken.for_user(user)
        accessToken = refreshToken.access_token
        utils.store_hashed_refresh(user, str(refreshToken))

        return setCookie(accessToken, refreshToken, user.role, user.id)


    @action(detail=False, methods=["delete"], url_path="logout", permission_classes=[IsAuthenticated])
    def logout(self, request):
        """
        DELETE /auth/logout
        - Reads the refreshToken cookie
        - Blacklists it
        - Clears the stored hash
        - Deletes both JWT cookies
        """
        raw_refresh = request.COOKIES.get(Constants.REFRESH_TOKEN)
        if not raw_refresh:
            return Response(
                {"detail": "Refresh token cookie not found"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(raw_refresh)
            token.blacklist()
        except TokenError as e:
            # if it’s already expired/blacklisted etc
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        utils.clear_hashed_refresh(request.user)

        response = Response(status.HTTP_200_OK)

        # delete cookie on the scope of the whole website
        response.delete_cookie(Constants.ACCESS_TOKEN, path="/")
        response.delete_cookie(Constants.REFRESH_TOKEN, path="/")

        return response


def setCookie(accessToken, refreshToken, role, id) -> Response:
    response = Response({
        "role": role,
        "id": id
    }, status=200)

    response.set_cookie(
        Constants.ACCESS_TOKEN,
        str(accessToken),
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=int(Constants.ACCESS_TOKEN_LIFETIME.total_seconds())
    )

    response.set_cookie(
        Constants.REFRESH_TOKEN,
        str(refreshToken),
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=int(Constants.REFRESH_TOKEN_LIFETIME.total_seconds())
    )

    return response
