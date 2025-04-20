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
        - categories (comma‑separated UUIDs) e.g. ?categories=id1,id2

        If categories is provided, returns products linked to *all* of those categories.
        """
        querySet = ProductModel.objects.all()

        categoriesParam = request.query_params.get("categories")
        if categoriesParam:
            # split on comma and strip whitespace
            categoryIds = [c.strip() for c in categoriesParam.split(",") if c.strip()]
            for cat in categoryIds:
                querySet = querySet.filter(category_links__categoryId=cat)
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
