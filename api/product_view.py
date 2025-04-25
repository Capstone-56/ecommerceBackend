from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action

from base.abstractModels import PagedList
from base.models import ProductModel
from .serializers import ProductModelSerializer

class ProductViewSet(viewsets.ViewSet):
    """
    A ViewSet for the ProductModel, enabling CRUD operations to be used on
    product data.
    """

    def list(self, request):
        """
        GET /api/product/
        Optional query params:
        - page (int)
        - page_size (int)
        - color (string) e.g. ?color=red
        - price_min (float) e.g. ?price_min=10.0
        - price_max (float) e.g. ?price_max=100.0
        - categories (comma‑separated UUIDs) e.g. ?categories=id1,id2

        If categories is provided, returns products linked to *all* of those categories.
        """
        querySet = ProductModel.objects.all()

        categoriesParam = request.query_params.get("categories")
        if categoriesParam:
            # split on comma and strip whitespace
            categoryIds = [c.strip() for c in categoriesParam.split(",") if c.strip()]
            for cat in categoryIds:
                querySet = querySet.filter(category_links__category=cat)
            querySet = querySet.distinct()

        # Colour filtering (by variant value)
        color = request.query_params.get("color")
        if color:
            querySet = querySet.filter(
                productconfig__variantId__variationTypeId__name__iexact="Color",
                productconfig__variantId__value__iexact=color
            ).distinct()

        # Price filtering (by related ProductItem)
        price_min = request.query_params.get("price_min")
        price_max = request.query_params.get("price_max")
        if price_min:
            querySet = querySet.filter(items__price__gte=price_min)
        if price_max:
            querySet = querySet.filter(items__price__lte=price_max)
        querySet = querySet.distinct()

        paginator = PagedList()
        pagedQuerySet = paginator.paginate_queryset(querySet, request)

        serializer = ProductModelSerializer(pagedQuerySet, many=True)
        return paginator.get_paginated_response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Retrieve a specific ProductModel record based on an id.
        GET /api/product/{id}
        """
        product = get_object_or_404(ProductModel, id=pk)
        serializer = ProductModelSerializer(product)

        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='featured')
    def featured(self, request):
        """
        Retrieve a set of three featured products.
        GET /api/product/featured
        """
        featured_products = ProductModel.objects.filter(featured=True)[:3]
        serializer = ProductModelSerializer(featured_products, many=True)

        return Response(serializer.data)
