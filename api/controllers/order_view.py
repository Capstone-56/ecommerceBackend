from django.shortcuts import get_object_or_404
from django.http import HttpResponseBadRequest

from rest_framework import viewsets, status
from rest_framework.response import Response

from base.abstractModels import PagedList
from base.models import OrderModel
from base.enums import ORDER_STATUS
from api.serializers import OrderSerializer, OrderListSerializer

class OrderViewSet(viewsets.ViewSet):
    def list(self, request):
        """
        Retrieve orders with filtering and pagination.
        GET /api/order
        Optional query params:
        - userIds (comma‑separated strings): user GUIDs e.g. ?userIds=uuid1,uuid2
        - shippingAddresses (comma‑separated strings): address GUIDs e.g. ?shippingAddresses=uuid1,uuid2  
        - shippingVendors (comma‑separated strings): shipping vendor IDs e.g. ?shippingVendors=1,2
        - status (ORDER_STATUS): Order status e.g. ?status=pending
        - page (int): Page number
        - pageSize (int): Number of items per page
        """
        orders = OrderModel.objects.all()
        
        # Filter by user IDs
        userIdsParam = request.query_params.get("userIds")
        if userIdsParam:
            userIds = [uid.strip() for uid in userIdsParam.split(',') if uid.strip()]
            orders = orders.filter(user_id__in=userIds)
        
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
        
        serializer = OrderListSerializer(page, many=True)
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
        Create a new order with order items.
        POST /api/order
        Body payload: {
            "userId": "uuid",
            "addressId": "uuid", 
            "shippingVendorId": 1,
            "totalPrice": 99.99,
            "status": "pending",
            "items": [
                {
                    "productItemId": "uuid",
                    "quantity": 2,
                    "price": 49.99
                }
            ]
        }
        """
        serializer = OrderSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return HttpResponseBadRequest(serializer.errors)
