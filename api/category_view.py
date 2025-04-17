from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.response import Response

from base.models import CategoryModel
from .serializers import CategoryModelSerializer

class CategoryViewSet(viewsets.ViewSet):
    """
    A ViewSet for the CategoryModel that lists all categories
    """
    def list(self, request):
        """
        Retrieve all CategoryModel records.
        GET /api/category
        """
        categories = CategoryModel.objects.all()
        serializer = CategoryModelSerializer(categories, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """
        Retrieve a specific CategoryModel record by ID.
        GET /api/category/{id}
        """
        category = get_object_or_404(CategoryModel, id=pk)
        serializer = CategoryModelSerializer(category)
        return Response(serializer.data)