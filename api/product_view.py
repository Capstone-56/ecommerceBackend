from rest_framework import viewsets
from rest_framework.response import Response

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
        """
        products = ProductModel.objects.all()
        serializer = ProductModelSerializer(products, many=True)
        return Response(serializer.data)
