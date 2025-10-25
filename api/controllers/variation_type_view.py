from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from base.models.variant_model import VariantModel
from rest_framework import viewsets
from rest_framework.response import Response

from api.serializers import VariationTypeSerializer
from base.models.variation_type_model import VariationTypeModel

class VariationTypeViewSet(viewsets.ViewSet):
    """
    A ViewSet for the VariantModel that lists all variations based on given ID.
    """
    def list(self, request):
        """
        Retrieve all variant records of a specific ID.
        GET /api/variation?category={categoryId}
        """
        category_id = request.query_params.get("category")
        filtered_category_variants = VariationTypeModel.objects.filter(category=category_id)
        serializer = VariationTypeSerializer(filtered_category_variants, many=True)
        return Response(serializer.data)
