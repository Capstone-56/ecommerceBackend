from django.contrib.auth.hashers import make_password, check_password
from base import Constants

def store_hashed_refresh(user, raw_refresh_token):
    """
    Hash & save the raw refresh token on the user.
    """
    user.refreshToken = make_password(raw_refresh_token)
    user.save(update_fields=[Constants.REFRESH_TOKEN])

def verify_hashed_refresh(user, raw_refresh_token):
    """
    Check a raw token against the stored hash.
    """
    return check_password(raw_refresh_token, user.refreshToken)
