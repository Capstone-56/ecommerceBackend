from django.db.models import Sum, Count
from django.utils.dateparse import parse_datetime
from django.http import HttpResponseBadRequest

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response

from base.models import OrderItemModel, ProductItemModel, ProductModel
from api.serializers import ProductItemModelSerializer, ProductModelSerializer

class OrderItemViewSet(viewsets.ViewSet):
    # TODO: Add role checking (admin only)
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="mostPurchasedProductItems")
    def most_purchased_product_items(self, request):
        """
        GET /api/orderItem/mostPurchasedProductItems
        Returns the most purchased product items.
        Query parameters:
        - limit: Number of items to return (default: 5)
        - orderBy: 'asc' for ascending or 'desc' for descending (default: 'desc')
        - startDate: Filter orders from this date (ISO format)
        - endDate: Filter orders until this date (ISO format)
        """
        limit = int(request.query_params.get("limit", 5))
        order_by = request.query_params.get("orderBy", "desc").lower()
        start_date = request.query_params.get("startDate")
        end_date = request.query_params.get("endDate")
        
        base_query = OrderItemModel.objects.select_related("productItem", "productItem__product", "order")
        
        if start_date:
            try:
                start_date_parsed = parse_datetime(start_date)
                if start_date_parsed:
                    base_query = base_query.filter(order__createdAt__gte=start_date_parsed)
            except ValueError:
                return HttpResponseBadRequest("Invalid start date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")
        
        if end_date:
            try:
                end_date_parsed = parse_datetime(end_date)
                if end_date_parsed:
                    base_query = base_query.filter(order__createdAt__lte=end_date_parsed)
            except ValueError:
                return HttpResponseBadRequest("Invalid end date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")
        
        # Group by product item and calculate total quantity
        product_items_data = (
            base_query
            .values("productItem")
            .annotate(total_quantity=Sum("quantity"))
            .order_by("-total_quantity" if order_by == "desc" else "total_quantity")
            [:limit]
        )
        
        # Get the actual ProductItem objects and serialize them
        product_item_ids = [item["productItem"] for item in product_items_data]
        product_items = ProductItemModel.objects.filter(id__in=product_item_ids).select_related("product")
        
        # Create a mapping of quantities
        quantity_map = {item["productItem"]: item["total_quantity"] for item in product_items_data}
        
        # Format response data using serializer
        response_data = []
        for product_item in product_items:
            serialized_data = ProductItemModelSerializer(product_item).data
            serialized_data["total_quantity_purchased"] = quantity_map[product_item.id]
            response_data.append(serialized_data)
        
        # Sort the response data by total_quantity_purchased
        response_data.sort(
            key=lambda x: x["total_quantity_purchased"],
            reverse=(order_by == "desc")
        )
        
        return Response(response_data)

    @action(detail=False, methods=["get"], url_path="mostPurchasedProducts")
    def most_purchased_products(self, request):
        """
        GET /api/orderItem/mostPurchasedProducts
        Returns the most purchased products (aggregated across all product items).
        Query parameters:
        - limit: Number of products to return (default: 5)
        - orderBy: 'asc' for ascending or 'desc' for descending (default: 'desc')
        - startDate: Filter orders from this date (ISO format)
        - endDate: Filter orders until this date (ISO format)
        """
        limit = int(request.query_params.get("limit", 5))
        order_by = request.query_params.get("orderBy", "desc").lower()
        start_date = request.query_params.get("startDate")
        end_date = request.query_params.get("endDate")
        
        base_query = OrderItemModel.objects.select_related("productItem", "productItem__product", "order")
        
        if start_date:
            try:
                start_date_parsed = parse_datetime(start_date)
                if start_date_parsed:
                    base_query = base_query.filter(order__createdAt__gte=start_date_parsed)
            except ValueError:
                return HttpResponseBadRequest("Invalid start date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")
        
        if end_date:
            try:
                end_date_parsed = parse_datetime(end_date)
                if end_date_parsed:
                    base_query = base_query.filter(order__createdAt__lte=end_date_parsed)
            except ValueError:
                return HttpResponseBadRequest("Invalid end date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")
        
        # Group by product and calculate total quantity across all product items
        products_data = (
            base_query
            .values("productItem__product")
            .annotate(
                total_quantity=Sum("quantity"),
                total_items_sold=Count("productItem", distinct=True)
            )
            .order_by("-total_quantity" if order_by == "desc" else "total_quantity")
            [:limit]
        )
        
        # Get the actual Product objects and serialize them
        product_ids = [item["productItem__product"] for item in products_data]
        products = ProductModel.objects.filter(id__in=product_ids)
        
        # Create a mapping of quantities and items sold
        data_map = {
            item["productItem__product"]: {
                "total_quantity": item["total_quantity"],
                "total_items_sold": item["total_items_sold"]
            }
            for item in products_data
        }
        
        # Format response data using serializer
        response_data = []
        for product in products:
            serialized_data = ProductModelSerializer(product).data
            product_data = data_map[product.id]
            serialized_data["total_quantity_purchased"] = product_data["total_quantity"]
            serialized_data["total_items_sold"] = product_data["total_items_sold"]
            response_data.append(serialized_data)
        
        # Sort the response data by total_quantity_purchased
        response_data.sort(
            key=lambda x: x["total_quantity_purchased"],
            reverse=(order_by == "desc")
        )
        
        return Response(response_data)
