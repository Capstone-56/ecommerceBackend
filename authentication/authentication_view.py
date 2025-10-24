import boto3

from django.http import HttpResponseBadRequest

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from api.serializers import UserModelSerializer
from api.services.mfa_service import TOTPMFAService

from base import Constants
from base import utils
from base.enums import ROLE
from base.models import *

from ecommerceBackend import settings

from django.utils.http import urlsafe_base64_encode
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import PasswordResetTokenGenerator

from .email_templates import password_reset_email

# Token generator for resetting passwords.
token_generator = PasswordResetTokenGenerator()
# AWS email service.
ses_client = boto3.client("ses", 
                          region_name="ap-southeast-2",
                          aws_access_key_id=settings.AWS_ACCESS_KEY,
                          aws_secret_access_key=settings.AWS_SECRET_KEY)

class AuthenticationViewSet(viewsets.ViewSet):
    """
    Handles user authentication operations like sign-up, login, token refresh, 2FA, etc.
    """
    mfa_service = TOTPMFAService()

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

            return setCookie(accessToken, refreshToken, user)

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

        if user.mfa_enabled:
            response = Response({"mfaRequired": True}, status=status.HTTP_200_OK)
            
            # Set HTTP-only cookies for MFA state
            response.set_cookie(
                Constants.CookieName.MFA_REQUIRED,
                "true",
                httponly=True,
                secure=True,
                samesite="Lax",
                max_age=int(Constants.MFA_STATE_LIFETIME.total_seconds())
            )
            response.set_cookie(
                Constants.CookieName.MFA_USER_ID,
                str(user.id),
                httponly=True,
                secure=True,
                samesite="Lax",
                max_age=int(Constants.MFA_STATE_LIFETIME.total_seconds())
            )
            
            return response

        # Issue JWTs for non-MFA users
        refreshToken = RefreshToken.for_user(user)
        accessToken = refreshToken.access_token
        utils.store_hashed_refresh(user, str(refreshToken))

        return setCookie(accessToken, refreshToken, user)


    @action(detail=False, methods=["get"], url_path="mfa-method", permission_classes=[AllowAny])
    def select_mfa_method(self, request):
        """
        User selects MFA method and receives code
        GET /auth/mfa-method?method=email or sms
        """
        # Verify MFA state from HTTP-only cookies
        if request.COOKIES.get(Constants.CookieName.MFA_REQUIRED) != "true":
            return HttpResponseBadRequest("MFA not required for this session")
        
        user_id = request.COOKIES.get(Constants.CookieName.MFA_USER_ID)
        if not user_id:
            return HttpResponseBadRequest("Invalid MFA session")
        
        try:
            user = UserModel.objects.get(id=user_id, mfa_enabled=True)
        except UserModel.DoesNotExist:
            return HttpResponseBadRequest("Invalid user or MFA not enabled")
        
        method = request.query_params.get("method")
        if not method or method not in ["email", "sms"]:
            return HttpResponseBadRequest("Invalid method.")
            
        if method == "email":
            success = self.mfa_service.send_mfa_code_email(user)
        elif method == "sms":
            if not user.phone:
                return HttpResponseBadRequest("Phone number not available for SMS")
            success = self.mfa_service.send_mfa_code_sms(user)
        
        if success:
            # Set MFA method in HTTP-only cookie
            response = Response(
                {
                    "message": f"MFA code sent via {method}"
                }, 
                status=status.HTTP_200_OK
            )
            response.set_cookie(
                Constants.CookieName.MFA_METHOD,
                method,
                httponly=True,
                secure=True,
                samesite="Lax",
                max_age=int(Constants.MFA_STATE_LIFETIME.total_seconds())
            )
            
            return response
        else:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(detail=False, methods=["post"], url_path="login-mfa", permission_classes=[AllowAny])
    def login_mfa(self, request):
        """
        Complete login with MFA verification
        POST /auth/login-mfa
        Request body JSON:
        {
          "code": "123456"
        }
        """
        # Verify MFA state from HTTP-only cookies
        if request.COOKIES.get(Constants.CookieName.MFA_REQUIRED) != "true":
            return HttpResponseBadRequest("MFA not required for this session")
        
        user_id = request.COOKIES.get(Constants.CookieName.MFA_USER_ID)
        if not user_id:
            return HttpResponseBadRequest("Invalid MFA session")
        
        try:
            user = UserModel.objects.get(id=user_id, mfa_enabled=True)
        except UserModel.DoesNotExist:
            return HttpResponseBadRequest("Invalid user or MFA not enabled")
        
        code = request.data.get("code")
        if not code:
            return HttpResponseBadRequest("MFA code is required")

        if not self.mfa_service.verify_mfa_code(user, code):
            return HttpResponseBadRequest("Invalid or expired MFA code")

        # Issue JWTs after successful MFA verification
        refreshToken = RefreshToken.for_user(user)
        accessToken = refreshToken.access_token
        utils.store_hashed_refresh(user, str(refreshToken))

        # Clear MFA cookies and complete authentication
        response = setCookie(accessToken, refreshToken, user)
        
        response.delete_cookie(Constants.CookieName.MFA_REQUIRED, path="/")
        response.delete_cookie(Constants.CookieName.MFA_USER_ID, path="/")
        response.delete_cookie(Constants.CookieName.MFA_METHOD, path="/")
        
        return response


    @action(detail=False, methods=["delete"], url_path="logout", permission_classes=[AllowAny])
    def logout(self, request):
        """
        DELETE /auth/logout
        - Reads the refreshToken cookie (if present)
        - Blacklists it (if valid)
        - Clears the stored hash (if user is authenticated)
        - Deletes both JWT cookies
        - Always returns 200 OK (idempotent operation)
        """
        raw_refresh = request.COOKIES.get(Constants.CookieName.REFRESH_TOKEN)
        
        # Try to blacklist the refresh token if it exists and is valid
        if raw_refresh:
            try:
                token = RefreshToken(raw_refresh)
                token.blacklist()
            except TokenError:
                # Token is already expired/blacklisted/invalid - that's fine
                pass

        # Clear the stored hash if the user is authenticated
        if request.user and request.user.is_authenticated:
            utils.clear_hashed_refresh(request.user)

        # Always clear cookies and return success
        response = Response({"detail": "Logged out successfully"}, status=status.HTTP_200_OK)
        response.delete_cookie(Constants.CookieName.ACCESS_TOKEN, path="/")
        response.delete_cookie(Constants.CookieName.REFRESH_TOKEN, path="/")
        
        # Clear MFA state cookies
        response.delete_cookie(Constants.CookieName.MFA_REQUIRED, path="/")
        response.delete_cookie(Constants.CookieName.MFA_USER_ID, path="/")
        response.delete_cookie(Constants.CookieName.MFA_METHOD, path="/")

        return response
    
    @action(detail=False, methods=["post"], url_path="forgot", permission_classes=[AllowAny])
    def forgot_password(self, request):
        """
        POST /auth/forgot
        Sends a password reset email to the given email if registered to a user.
        Request Body:
        {
            email: "admin@test.com"
        }
        """
        try:
            user = UserModel.objects.get(email=request.data["email"])
        except UserModel.DoesNotExist:
            # For security, don't reveal whether the email exists and return success response
            # regardless.
            return Response(status=status.HTTP_200_OK)

        # Encode the email to be present in the url.
        email = urlsafe_base64_encode(force_bytes(user.email))
        # Generate a valid token for a user to use to reset the password.
        token = token_generator.make_token(user)

        # Dynamically change the frontend URL based on environment.
        frontend_base = (
            settings.FRONTEND_URL_LOCAL
            if settings.DEBUG
            else settings.FRONTEND_URL_PROD
        )

        # The reset URL to put in the email.
        reset_url = f"{frontend_base}/reset/{email}/{token}"

        try:
            # Send the email using the client. Utilises the password reset email template
            # in the email_templates.py file.
            ses_client.send_email(
                Source=password_reset_email.sender_email,
                Destination={'ToAddresses': [user.email]},
                Message={
                    'Subject': {'Data': password_reset_email.subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Html': {'Data': password_reset_email.body_html + "<br />" + "Reset Link: " + reset_url, 'Charset': 'UTF-8'},
                    }
                }
            )
            return Response(status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": "Failed to send email"}, status=500)
        
    @action(detail=False, methods=["post"], url_path="reset-password", permission_classes=[AllowAny])
    def reset_password(self, request):
        """
        POST /auth/reset-password
        Updates the users password with a new supplied one. Must have the valid token
        present in url along with base64 encoded email.
        Request Body:
        {
            email: "eGF2ZTg4OUBnbWFpbC5jb20",
            token: "cxk3j1-92f71924ed6cebb394a1a4adf9b75a82",
            new_password: "new-password"
        }
        """
        try:
            email = urlsafe_base64_decode(request.data["email"]).decode()
            user = UserModel.objects.get(email=email)
        except Exception:
            return Response({"detail": "Invalid link."}, status=status.HTTP_400_BAD_REQUEST)

        if not token_generator.check_token(user, request.data["token"]):
            return Response({"detail": "Token invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)

        new_password = request.data.get("new_password")
        if not new_password:
            return Response({"detail": "Password required."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({"detail": "Password reset successful."}, status=status.HTTP_200_OK)


def setCookie(accessToken, refreshToken, user) -> Response:
    response = Response({
        "role": user.role,
        "id": user.id,
        "username": user.username
    }, status=200)

    response.set_cookie(
        Constants.CookieName.ACCESS_TOKEN,
        str(accessToken),
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=int(Constants.ACCESS_TOKEN_LIFETIME.total_seconds())
    )

    response.set_cookie(
        Constants.CookieName.REFRESH_TOKEN,
        str(refreshToken),
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=int(Constants.REFRESH_TOKEN_LIFETIME.total_seconds())
    )

    return response
