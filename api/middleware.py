from base.constants import Constants

class RefreshCookieMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # authenticate request
        response = self.get_response(request)

        # issue new access token if the current expired
        new_access = getattr(request, "_access", None)
        
        # Also check session if request attribute is not found
        if not new_access and hasattr(request, "session"):
            new_access = request.session.get("_new_access_token")
            
            if new_access:
                # Clear from session after using
                del request.session["_new_access_token"]
        
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
