from django.http import HttpResponseNotFound, HttpResponseBadRequest

from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action

from base.models import ProductConfigModel, ProductItemModel

from api.serializers import ProductItemModelSerializer

class ProductItemViewSet(viewsets.ViewSet):
    def create(self, request):
        serializer = ProductItemModelSerializer(data=request.data, context={"request": request})
        print(request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return HttpResponseBadRequest(serializer.errors)

    @action(detail=True, methods=["post"], url_path="configurations")
    def retrieveByConfigurations(self, request, pk):
        """
        Retrieve a product item by productId and its configurations.
        POST /api/productItem/{productId}/configurations
        body payload:
        {
            "variantIds": list<string>
        }
        """
        variant_ids = request.data.get("variantIds", [])

        if not variant_ids:
            return HttpResponseBadRequest("Variant IDs are required")
        
        matching_item = None
        
        # Get all ProductItems for this product and check each one
        product_items = ProductItemModel.objects.filter(product_id=pk)
        for item in product_items:
            # Get all variant IDs for this ProductItem
            item_variant_ids = list(
                ProductConfigModel.objects.filter(productItem=item)
                .values_list("variant_id", flat=True)
            )
            
            # Convert to sets for easy comparison
            item_variants_set = set(str(vid) for vid in item_variant_ids)  # cast GUIDs to strings
            target_variants_set = set(variant_ids)
            
            # Check if this item has exactly the variants we want
            if item_variants_set == target_variants_set:
                if matching_item is None:
                    matching_item = item
                else:
                    # Found multiple items with same configuration - this shouldn't happen
                    return HttpResponseBadRequest("Multiple product items found with these configurations")

        if matching_item is None:
            return HttpResponseNotFound()

        serializer = ProductItemModelSerializer(matching_item)
        return Response({"id": serializer.data["id"]})
    
    @action(detail=True, methods=["get"], url_path="byProduct")
    def getByProductId(self, request, pk):
        """
        Get all product items for a given productId.
        GET /api/productItem/{productId}/byProduct
        """
        product_items = ProductItemModel.objects.filter(product_id=pk).order_by("id")

        serializer = ProductItemModelSerializer(product_items, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="delete")
    def delete_product_item(self, request, pk):
        """
        Get all product items for a given productId.
        GET /api/productItem/{productItemId}/delete
        """
        product_item_to_delete = get_object_or_404(ProductItemModel, id=pk)
        product_item_to_delete.delete()

        return Response(status=status.HTTP_200_OK)
    