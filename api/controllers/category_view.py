from django.shortcuts import get_object_or_404
from django.db import transaction
from django.core.exceptions import ValidationError

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny

from base.models import CategoryModel

from api.serializers import CategoryModelSerializer, FlatCategorySerializer

class CategoryViewSet(viewsets.ViewSet):
    """
    A ViewSet for the CategoryModel that provides full CRUD operations
    with tree structure support
    """
    def get_permissions(self):
        if self.action in ["create", "update", "destroy", "flat-list"]:
            return [IsAuthenticated()]

        return [AllowAny()]

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
        GET /api/category/{internalName}
        """
        category = get_object_or_404(CategoryModel, internalName=pk)
        serializer = CategoryModelSerializer(category, context={"request": request})
        return Response(serializer.data)

    def create(self, request):
        """
        Create a new category.
        POST /api/category
        
        Body:
        {
            "name": "Category Name",
            "description": "Category description",
            "parentCategory": "parent_internal_name" (optional)
        }
        """
        try:
            with transaction.atomic():
                serializer = CategoryModelSerializer(data=request.data, context={"request": request})
                if serializer.is_valid():
                    category = serializer.save()

                    return Response(
                        CategoryModelSerializer(category, context={"request": request}).data, 
                        status=status.HTTP_201_CREATED
                    )

                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        """
        Update an existing category.
        PUT /api/category/{internalName}
        
        Body:
        {
            "name": "Updated Name",  (display name - does NOT change internalName)
            "description": "Updated description",
            "parentCategory": "new_parent_internal_name" (optional)
        }
        """
        try:
            with transaction.atomic():
                category = get_object_or_404(CategoryModel, internalName=pk)
                serializer = CategoryModelSerializer(
                    category, 
                    data=request.data, 
                    partial=True, 
                    context={"request": request}
                )
                if serializer.is_valid():
                    updated_category = serializer.save()
                    return Response(
                        CategoryModelSerializer(updated_category, context={"request": request}).data
                    )
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        """
        Delete a category and all its descendants.
        DELETE /api/category/{internalName}
        
        Query params:
        - moveChildren=<parent_internal_name>: Move children to specified parent before deletion
        
        Returns:
        - 204 No Content: If no children were moved
        - 200 OK with new parent tree: If children were moved to a new parent
        """
        try:
            with transaction.atomic():
                category = get_object_or_404(CategoryModel, internalName=pk)
                move_children_to = request.query_params.get("moveChildren")
                
                new_parent = None
                if move_children_to:
                    # Move children to new parent before deletion
                    new_parent = get_object_or_404(CategoryModel, internalName=move_children_to)
                    children = category.get_children()
                    for child in children:
                        child.parentCategory = new_parent
                        child.save()
                
                category.delete()
                
                # If children were moved, return the updated parent tree
                if new_parent:
                    # Re-fetch to get fresh MPTT tree data after deletion
                    fresh_parent = CategoryModel.objects.get(internalName=new_parent.internalName)
                    return Response(
                        CategoryModelSerializer(fresh_parent, context={"request": request}).data,
                        status=status.HTTP_200_OK
                    )
                
                return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"], url_path="flat-list")
    def flat_list(self, request):
        """
        Admin endpoint: Returns all categories in a flat list.
        GET /api/category/flat-list
        """
        all_categories = CategoryModel.objects.all().order_by("internalName")
        serializer = FlatCategorySerializer(all_categories, many=True)
        return Response(serializer.data)
