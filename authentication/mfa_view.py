from django.http import HttpResponseBadRequest

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

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
    
