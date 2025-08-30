from django.shortcuts import get_object_or_404
from django.http import HttpResponseBadRequest

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from base.abstractModels import PagedList
from base.models import OrderModel
from base.enums import ORDER_STATUS
from api.serializers import OrderSerializer, ListOrderSerializer, CreateGuestOrderSerializer, CreateAuthenticatedOrderSerializer

class OrderViewSet(viewsets.ViewSet):
    def get_permissions(self):
        if self.action == "list":
            return [IsAuthenticated()]
        
        return [AllowAny()]
    
    def list(self, request):
        """
        Retrieve orders with filtering and pagination.
        GET /api/order
        Optional query params:
        - userNames (comma‑separated strings): usernames e.g. ?userNames=john_doe,jane_smith
        - shippingAddresses (comma‑separated strings): address GUIDs e.g. ?shippingAddresses=uuid1,uuid2  
        - shippingVendors (comma‑separated strings): shipping vendor IDs e.g. ?shippingVendors=1,2
        - status (ORDER_STATUS): Order status e.g. ?status=pending
        - page (int): Page number
        - pageSize (int): Number of items per page
        """
        orders = OrderModel.objects.all()
        
        # Filter by usernames
        userNamesParam = request.query_params.get("userNames")
        if userNamesParam:
            userNames = [username.strip() for username in userNamesParam.split(',') if username.strip()]
            orders = orders.filter(user__username__in=userNames)
        
        # Filter by shipping addresses
        shippingAddressesParam = request.query_params.get("shippingAddresses")
        if shippingAddressesParam:
            shippingAddresses = [aid.strip() for aid in shippingAddressesParam.split(',') if aid.strip()]
            orders = orders.filter(address_id__in=shippingAddresses)
        
        # Filter by shipping vendors
        shippingVendorsParam = request.query_params.get("shippingVendors")
        if shippingVendorsParam:
            shippingVendors = [vid.strip() for vid in shippingVendorsParam.split(',') if vid.strip()]
            orders = orders.filter(shippingVendor_id__in=shippingVendors)
        
        # Filter by status
        statusParam = request.query_params.get("status")
        if statusParam:
            # Validate status is in ORDER_STATUS enum
            valid_statuses = [status.value for status in ORDER_STATUS]
            if statusParam in valid_statuses:
                orders = orders.filter(status=statusParam)
        
        # Order by creation date (most recent first)
        orders = orders.order_by("-createdAt")
        
        # Pagination
        paginator = PagedList()
        page = paginator.paginate_queryset(orders, request)
        
        serializer = ListOrderSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def retrieve(self, request, pk=None):
        """
        Retrieve a specific order by ID with order items.
        GET /api/order/{id}
        """
        order = get_object_or_404(OrderModel, id=pk)
        serializer = OrderSerializer(order)
        return Response(serializer.data)

    def create(self, request):
        """
        Create a new order with order items for both authenticated and guest users.
        
        Authentication Detection:
        - Authenticated users: Valid JWT token in httpOnly cookie
        - Guest users: No valid JWT token OR guest-specific fields present
        
        For authenticated users (JWT cookie present):
        POST /api/order
        {
            "addressId": uuid, 
            "shippingVendorId": 1,
            "items": [
                {
                    "productItemId": uuid,
                    "quantity": 2
                }
            ]
        }
        Note: 'user' and 'totalPrice' are auto-populated by backend
        
        For guest users (no JWT cookie OR guest fields present),
        Every guest order creates a new anonymous guest user:
        POST /api/order
        {
            "email": "guest@example.com",
            "firstName": "Jane",
            "lastName": "Smith",
            "phone": "1234567890",
            "addressId": uuid,
            "shippingVendorId": 1,
            "items": [
                {
                    "productItemId": uuid,
                    "quantity": 2
                }
            ]
        }
        Note: 'totalPrice' and item 'price' are auto-calculated by backend
        """
        # Check if user is authenticated (has valid JWT in httpOnly cookie)
        is_authenticated = request.user and request.user.is_authenticated
        
        # Check if this has user info fields (indicates guest order when not authenticated)
        has_user_info_fields = any(field in request.data for field in ["email", "firstName", "lastName"])
        
        # Determine if this is a guest order: user info provided but not authenticated
        is_guest_order = has_user_info_fields and not is_authenticated
        
        if is_guest_order:
            # Use guest order serializer
            serializer = CreateGuestOrderSerializer(data=request.data)
        else:
            # Use authenticated user order serializer - auto-assign current user if not provided
            order_data = request.data.copy()
            if "user_id" not in order_data:
                order_data["user_id"] = request.user.id
            serializer = CreateAuthenticatedOrderSerializer(data=order_data)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return HttpResponseBadRequest(serializer.errors)
