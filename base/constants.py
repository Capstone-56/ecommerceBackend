from datetime import timedelta

class Constants:
    DEFAULT_PAGINATOR_PAGE_SIZE = 10
    ACCESS_TOKEN_LIFETIME = timedelta(minutes=60)
    REFRESH_TOKEN_LIFETIME = timedelta(days=1)
    ACCESS_TOKEN = "accessToken"
    REFRESH_TOKEN = "refreshToken"
    