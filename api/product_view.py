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
        Retrieve all ProductModel records.
        GET /api/product
        Query params:
        - page: nullable number (the specific paged list client wants to retrieve from)
        - page_size: nullable number (number of items client wants to return, default is 10)
        """
        products = ProductModel.objects.all()
        paginator = PagedList()

        result_page = paginator.paginate_queryset(products, request)
        serializer = ProductModelSerializer(result_page, many=True)

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
