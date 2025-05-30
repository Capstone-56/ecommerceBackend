from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.response import Response

from base.models import CategoryModel
from api.serializers import CategoryModelSerializer

class CategoryViewSet(viewsets.ViewSet):
    """
    A ViewSet for the CategoryModel that lists all categories
    """
    def list(self, request):
        """
        Retrieve all CategoryModel records.
        GET /api/category
        """
        # Only get categories where parentCategory is None
        top_level_categories = CategoryModel.objects.filter(parentCategory__isnull=True)
        serializer = CategoryModelSerializer(top_level_categories, many=True, context={"request": request, "view": self})
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """
        Retrieve a specific CategoryModel record by ID.
        GET /api/category/{id}
        """
        category = get_object_or_404(CategoryModel, internalName=pk)
        serializer = CategoryModelSerializer(category)
        return Response(serializer.data)
