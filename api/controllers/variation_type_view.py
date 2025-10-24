from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.response import Response

from base.models import VariationTypeModel, VariantModel
from api.serializers import VariationTypeSerializer

class VariationTypeViewSet(viewsets.ViewSet):
    """
    A ViewSet for VariationType with full CRUD operations and nested Variant management.
    """
    
    def list(self, request):
        """
        Retrieve all variation types, optionally filtered by category.
        GET /api/variation
        GET /api/variation?category={categoryInternalName}
        """
        category_internal_name = request.query_params.get("category")
        
        if category_internal_name:
            variation_types = VariationTypeModel.objects.filter(
                categories__internalName=category_internal_name
            ).distinct()
        else:
            variation_types = VariationTypeModel.objects.all()
        
        serializer = VariationTypeSerializer(variation_types, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Retrieve a specific variation type by ID.
        GET /api/variation/{id}
        """
        variation_type = get_object_or_404(VariationTypeModel, id=pk)
        serializer = VariationTypeSerializer(variation_type)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Create a new variation type with nested variations.
        POST /api/variation
        Body: {
            "name": "Size",
            "categories": ["shoes", "clothing"],
            "variations": [
                {"value": "Small"},
                {"value": "Large"}
            ]
        }
        """
        try:
            with transaction.atomic():
                serializer = VariationTypeSerializer(data=request.data)
                if serializer.is_valid():
                    variation_type = serializer.save()
                    return Response(
                        VariationTypeSerializer(variation_type).data,
                        status=status.HTTP_201_CREATED
                    )
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, pk=None):
        """
        Update a variation type and its variations.
        PUT /api/variation/{id}
        Body: {
            "name": "Updated Size",
            "categories": ["shoes"],
            "variations": [
                {"id": "existing-uuid", "value": "Updated Small"},
                {"value": "New XL"}
            ]
        }
        """
        try:
            with transaction.atomic():
                variation_type = get_object_or_404(VariationTypeModel, id=pk)
                serializer = VariationTypeSerializer(
                    variation_type,
                    data=request.data,
                    partial=False
                )
                if serializer.is_valid():
                    updated = serializer.save()
                    return Response(VariationTypeSerializer(updated).data)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def partial_update(self, request, pk=None):
        """
        Partially update a variation type.
        PATCH /api/variation/{id}
        """
        try:
            with transaction.atomic():
                variation_type = get_object_or_404(VariationTypeModel, id=pk)
                serializer = VariationTypeSerializer(
                    variation_type,
                    data=request.data,
                    partial=True
                )
                if serializer.is_valid():
                    updated = serializer.save()
                    return Response(VariationTypeSerializer(updated).data)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, pk=None):
        """
        Delete a variation type and cascade delete all its variants.
        DELETE /api/variation/{id}
        """
        try:
            with transaction.atomic():
                variation_type = get_object_or_404(VariationTypeModel, id=pk)
                variation_type.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
