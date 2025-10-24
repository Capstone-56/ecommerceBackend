from datetime import timedelta

class Constants:
    DEFAULT_PAGINATOR_PAGE_SIZE = 10
    ACCESS_TOKEN_LIFETIME = timedelta(minutes=60)
    REFRESH_TOKEN_LIFETIME = timedelta(days=1)
    MFA_STATE_LIFETIME = timedelta(minutes=5)

    class CookieName:
        ACCESS_TOKEN = "accessToken"
        REFRESH_TOKEN = "refreshToken"
        MFA_REQUIRED = "mfaRequired"
        MFA_USER_ID = "mfaUserId"
        MFA_METHOD = "mfaMethod"
