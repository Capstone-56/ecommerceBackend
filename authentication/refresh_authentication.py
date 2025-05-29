from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.backends import TokenBackend
from django.contrib.auth import get_user_model
from base.utils import verify_hashed_refresh
from base import Constants

User = get_user_model()

class RefreshAuthentication(JWTAuthentication):
    """
    Default authentication class, customising based on JWTAuthentication class
    Try to authenticate via the HttpOnly accessToken cookie.
    If it’s expired, decode it (ignoring expiry) to get userId.
    Lookup the user and verify they still have a valid (hashed) refresh in DB.
    Issue a brand-new access token via AccessToken.for_user(user).
    """
    def authenticate(self, request):
        rawAccess = request.COOKIES.get(Constants.ACCESS_TOKEN)
        if rawAccess:
            try:
                validated = self.get_validated_token(rawAccess)
                return self.get_user(validated), validated
            except TokenError:
                pass

        rawRefresh = request.COOKIES.get(Constants.REFRESH_TOKEN)
        if not rawRefresh:
            return None

        # Decode expired access to get user ID (ignoring expiry)
        try:
            tokenBackend = TokenBackend(
                algorithm=settings.SIMPLE_JWT["ALGORITHM"],
                signing_key=settings.SIMPLE_JWT["SIGNING_KEY"],
            )
            payload = tokenBackend.decode(rawAccess or "", verify=False)
            user_id = payload.get("id")
        except Exception:
            return None

        user = User.objects.filter(id=user_id).first()
        if not user or not verify_hashed_refresh(user, rawRefresh):
            return None

        newAccess = AccessToken.for_user(user)
        request._access = str(newAccess)

        validated = self.get_validated_token(request._access)
        return self.get_user(validated), validated
