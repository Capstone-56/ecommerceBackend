from django.shortcuts import get_object_or_404
from django.http import HttpResponseBadRequest

from rest_framework import viewsets, status
from rest_framework.response import Response

from base.models import ShippingVendorModel
from api.serializers import ShippingVendorSerializer

class ShippingVendorViewSet(viewsets.ViewSet):
    def list(self, request):
        """
        Retrieve all shipping vendors.
        GET /api/shippingVendor
        Optional query params:
        - isActive (bool): 
          * true => return only active vendors
          * false => return only inactive vendors
          * null/not provided => return all vendors
        """
        vendors = ShippingVendorModel.objects.all()
        
        # Filter by active status if requested
        isActiveParam = request.query_params.get("isActive")
        if isActiveParam is not None:
            isActive = isActiveParam.lower() == "true"
            vendors = vendors.filter(isActive=isActive)
            
        serializer = ShippingVendorSerializer(vendors, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """
        Retrieve a specific shipping vendor by ID.
        GET /api/shippingVendor/{id}
        """
        vendor = get_object_or_404(ShippingVendorModel, id=pk)
        serializer = ShippingVendorSerializer(vendor)
        return Response(serializer.data)

    def create(self, request):
        """
        Create a new shipping vendor.
        POST /api/shippingVendor
        Body payload: {
            "name": "Vendor Name", 
            "logoUrl": "https://...",
            "isActive": true
        }
        """
        serializer = ShippingVendorSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return HttpResponseBadRequest(serializer.errors)

    def update(self, request, pk=None):
        """
        Update an existing shipping vendor.
        PUT /api/shippingVendor/{id}
        Body payload: {
            "name": "Updated Name", 
            "logoUrl": "https://...",
            "isActive": true
        }
        """
        vendor = get_object_or_404(ShippingVendorModel, id=pk)
        serializer = ShippingVendorSerializer(vendor, data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return HttpResponseBadRequest(serializer.errors)
