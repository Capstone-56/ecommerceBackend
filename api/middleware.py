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
        
        # Check if authentication failed and signal client to clear auth state
        self.check_auth_state_sync(request, response)
        
        return response
    
    def check_auth_state_sync(self, request, response):
        """
        Signal client to clear authentication state if server detects invalid session.
        This helps keep client-side localStorage in sync with server-side authentication state.
        """
        # Check if this is an API request that requires authentication
        is_api_request = request.path.startswith("/api/")
        
        # Only check authentication state for protected endpoints
        # Skip for public endpoints like login, signup, etc.
        # TODO: separate public and authenticated endpoints
        public_endpoints = ["/auth/", "/api/location/coordinates-to-country"]
        is_public_endpoint = any(request.path.startswith(endpoint) for endpoint in public_endpoints)
        
        if is_api_request and not is_public_endpoint:
            # Check if user has auth cookies but is not authenticated
            has_access_token = bool(request.COOKIES.get(Constants.ACCESS_TOKEN))
            has_refresh_token = bool(request.COOKIES.get(Constants.REFRESH_TOKEN))
            was_authenticated = has_access_token or has_refresh_token
            
            if not request.user.is_authenticated:
                # Always clear auth state if not authenticated
                response["X-Clear-Auth-State"] = "true"
                
                # Only clear cart if user was previously authenticated
                if was_authenticated:
                    response["X-Clear-Auth-Cart"] = "true"
