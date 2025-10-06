from datetime import datetime, timedelta
from django.shortcuts import get_object_or_404
from django.http import HttpResponseBadRequest
from django.db.models import Sum
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action

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
        user_names_param = request.query_params.get("userNames")
        if user_names_param:
            user_names = [user_name.strip() for user_name in user_names_param.split(',') if user_name.strip()]
            orders = orders.filter(user__username__in=user_names)
        
        # Filter by shipping addresses
        shipping_addresses_param = request.query_params.get("shippingAddresses")
        if shipping_addresses_param:
            shipping_addresses = [aid.strip() for aid in shipping_addresses_param.split(',') if aid.strip()]
            orders = orders.filter(address_id__in=shipping_addresses)
        
        # Filter by shipping vendors
        shipping_vendors_param = request.query_params.get("shippingVendors")
        if shipping_vendors_param:
            shipping_vendors = [vid.strip() for vid in shipping_vendors_param.split(',') if vid.strip()]
            orders = orders.filter(shipments__shippingVendor_id__in=shipping_vendors)
        
        # Filter by status
        status_param = request.query_params.get("status")
        if status_param:
            # Validate status is in ORDER_STATUS enum
            valid_statuses = [status.value for status in ORDER_STATUS]
            if status_param in valid_statuses:
                orders = orders.filter(status=status_param)
        
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

    @action(detail=False, methods=["get"], url_path="totalSales")
    def total_sales(self, request):
        """
        Get total sales amount within a date range.
        GET /api/order/totalSales
        
        Query parameters:
        - startDate (ISO format YYYY-MM-DD): Start date for sales calculation
        - endDate (ISO format YYYY-MM-DD): End date for sales calculation
        - If no dates provided, defaults to last 7 days
        
        Returns:
        {
            "totalSales": 1234.56,
            "orderCount": 15
        }
        """
        start_date_param = request.query_params.get("startDate")
        end_date_param = request.query_params.get("endDate")
        
        # Set default date range (last 7 days) if not provided
        if not start_date_param or not end_date_param:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=7)
        else:
            try:
                start_date = datetime.strptime(start_date_param, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_param, '%Y-%m-%d').date()
            except ValueError:
                return HttpResponseBadRequest("Invalid date format. Use YYYY-MM-DD format.")
        
        # Validate date range
        if start_date > end_date:
            return HttpResponseBadRequest("Start date cannot be after end date.")
        
        # Filter orders by date range (include full end date by adding 1 day)
        end_date_inclusive = end_date + timedelta(days=1)
        orders = OrderModel.objects.filter(
            createdAt__gte=start_date,
            createdAt__lt=end_date_inclusive
        )
        
        # Calculate total sales and order count
        total_sales = orders.aggregate(total=Sum("totalPrice"))["total"] or 0
        order_count = orders.count()
        
        return Response({
            "totalSales": round(float(total_sales), 2),
            "orderCount": order_count
        })
    
    @action(detail=False, methods=["get"], url_path="weekly/sales")
    def weekly_sales(self, request):
        """
        Get total sales per day for the past week.
        GET /api/order/weekly/sales
        
        NOTE: This would return the sales for the past week and if there
              were no sales it then returns total_sales: 0.
        Returns:
        [   
            {
                date: 2025-09-03,
                total_sales: 3 
            },
            {
                date: 2025-09-04,
                total_sales: 7 
            }
        ]
        """

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=6)
        
        # Filter orders by date range (include full end date by adding 1 day)
        end_date_inclusive = end_date + timedelta(days=1)
        orders_per_day = (
                OrderModel.objects
                .filter(createdAt__gte=start_date, createdAt__lt=end_date_inclusive)
                .annotate(date=TruncDate("createdAt"))
                .values("date")
                .annotate(total_sales=Count("id"))
                .order_by("date")
            )
                
        # Convert queryset to dict keyed by date.
        sales_dict = {row["date"]: row["total_sales"] for row in orders_per_day}

        # Build full 7-day list.
        results = []
        for i in range((end_date - start_date).days + 1):
            date = start_date + timedelta(days=i)
            results.append({
                "date": date,
                "total_sales": sales_dict.get(date, 0)
            })
        
        return Response(results)

    @action(detail=False, methods=["post"], url_path="update")
    def update_order_status(self, request):
        """
        Updates and orders status.
        POST /api/order/update
        {
            id: BDNX#0001,
            status: shipped
        }
        """
        order = get_object_or_404(OrderModel, id=request.data["id"])
        order.status = request.data["updatedStatus"]
        order.save(update_fields=["status"])
        return Response({"message": "Status updated successfully"})
