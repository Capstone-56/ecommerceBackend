from django.http import HttpResponseBadRequest

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny

from base import Constants
from base.enums import *
from base.models import *

from api.services.mfa_service import TOTPMFAService

class MFAViewSet(viewsets.ViewSet):
    """
    Handles MFA operations for authenticated users
    """
    mfa_service = TOTPMFAService()

    @action(detail=False, methods=["put"], url_path="toggle", permission_classes=[IsAuthenticated])
    def toggle_mfa(self, request):
        """
        Enable or disable MFA for the authenticated user
        PUT /auth/mfa/toggle?enable=true
        PUT /auth/mfa/toggle?enable=false
        """
        enable_param = request.query_params.get("enable")
        
        if enable_param is None:
            return HttpResponseBadRequest("Missing 'enable' query parameter")
        
        if enable_param.lower() not in ["true", "false"]:
            return HttpResponseBadRequest("Invalid value for 'enable'")
        
        user = request.user
        enable = enable_param.lower() == "true"
        
        if enable:
            user.mfa_enabled = True
            user.save()
            
            self.mfa_service.generate_user_secret(user)
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            if user.role == ROLE.ADMIN.value or user.role == ROLE.MANAGER.value:
                return HttpResponseBadRequest("Admin and managers must have MFA enabled")

            user.mfa_enabled = False
            user.mfa_secret = None
            user.save()
            
            return Response(status=status.HTTP_204_NO_CONTENT)
    

    @action(detail=False, methods=["get"], url_path="resend", permission_classes=[AllowAny])
    def resend_code(self, request):
        """
        Resend MFA code
        GET /auth/mfa/resend?method=email or sms
        """
        # Get user ID from HTTP-only cookie
        user_id = request.COOKIES.get(Constants.CookieName.MFA_USER_ID)
        if not user_id:
            return HttpResponseBadRequest("Invalid MFA session")
        
        try:
            user = UserModel.objects.get(id=user_id, mfa_enabled=True)
        except UserModel.DoesNotExist:
            return HttpResponseBadRequest("Invalid user or MFA not enabled")
        
        method = request.query_params.get("method")
        if not method:
            return HttpResponseBadRequest("Method is required")
        
        if method not in ["email", "sms"]:
            return HttpResponseBadRequest("Invalid method.")

        if method == "email":
            success = self.mfa_service.send_mfa_code_email(user)
            if success:
                return Response(f"MFA code resent via email to {user.email}", status=status.HTTP_200_OK)
        elif method == "sms":
            if not user.phone:
                return HttpResponseBadRequest("Phone number not available for SMS")
            success = self.mfa_service.send_mfa_code_sms(user)
            if success:
                # Truncate phone to last 3 digits for privacy
                phone_last_3 = user.phone[-3:] if user.phone else "***"
                return Response(f"MFA code resent via SMS to ***{phone_last_3}", status=status.HTTP_200_OK)
        
        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
