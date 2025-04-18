from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action

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

    @action(detail=True, methods=['get'], url_path='subcategories')
    def get_all_subcategories(self, request, pk=None):
        """
        Retrieve all subcategories for a given category, including their names.
        GET /api/category/{id}/subcategories/

        This method returns a JSON response with the `id` and `name` of all
        immediate subcategories for a given category.
        """
        category = get_object_or_404(CategoryModel, id=pk)
        subcategories = CategoryModel.objects.filter(parentCategoryId=category.id)

        # Build a list of subcategories with id and name
        subcategory_data = [{"id": subcategory.id, "name": subcategory.name} for subcategory in subcategories]

        return Response({"subcategories": subcategory_data})