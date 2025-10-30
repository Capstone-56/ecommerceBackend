from django.conf import settings
from django.contrib.auth import get_user_model

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.backends import TokenBackend

from base.utils import verify_hashed_refresh
from base import Constants

# TODO: find out if this can use the UserModel from base
User = get_user_model()

class RefreshAuthentication(JWTAuthentication):
    """
    Custom default authentication class, customising based on JWTAuthentication class
    Try to authenticate via the HttpOnly accessToken cookie.
    If it’s expired, decode it (ignoring expiry) to get userId.
    Lookup the user and verify they still have a valid (hashed) refresh in DB.
    Issue a brand-new access token via AccessToken.for_user(user).
    """
    def authenticate(self, request):
        rawAccess = request.COOKIES.get(Constants.CookieName.ACCESS_TOKEN)
        rawRefresh = request.COOKIES.get(Constants.CookieName.REFRESH_TOKEN)
        
        if rawAccess:
            try:
                validated = self.get_validated_token(rawAccess)

                return self.get_user(validated), validated
            except TokenError as e:
                pass

        if not rawRefresh:
            return None

        # Try to get user ID from either expired access token or refresh token
        user_id = None
        
        # First try to decode expired access token if it exists
        if rawAccess:
            try:
                tokenBackend = TokenBackend(
                    algorithm=settings.SIMPLE_JWT["ALGORITHM"],
                    signing_key=settings.SIMPLE_JWT["SIGNING_KEY"],
                )
                payload = tokenBackend.decode(rawAccess, verify=False)
                user_id = payload.get("user_id")
            except Exception as e:
                pass
        
        # If no access token or failed to decode, get user ID from refresh token
        if not user_id:
            try:
                refresh_token = RefreshToken(rawRefresh)
                user_id = refresh_token.get("user_id")
            except Exception as e:
                return None

        user = User.objects.filter(id=user_id).first()
        if not user:
            return None
            
        if not verify_hashed_refresh(user, rawRefresh):
            return None

        newAccess = AccessToken.for_user(user)
        request._access = str(newAccess)
        
        # Also store in session for middleware to pick up
        if hasattr(request, "session"):
            request.session[Constants.Session.NEW_ACCESS_TOKEN] = str(newAccess)

        validated = self.get_validated_token(request._access)
        return self.get_user(validated), validated
