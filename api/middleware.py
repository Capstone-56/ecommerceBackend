from base.constants import Constants

class RefreshCookieMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        new_access = getattr(request, "_access", None)
        if new_access:
            response.set_cookie(
                Constants.ACCESS_TOKEN,
                new_access,
                httponly=True,
                secure=True,
                samesite="Lax",
                max_age=int(Constants.ACCESS_TOKEN_LIFETIME.total_seconds()),
            )
        return response
