from rest_framework import viewsets

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
