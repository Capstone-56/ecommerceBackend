from django.shortcuts import get_object_or_404
from django.http import HttpResponseBadRequest

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from base.models import ShipmentModel

from api.serializers import ShipmentSerializer, CreateShipmentSerializer, UpdateShipmentSerializer

class ShipmentViewSet(viewsets.ViewSet):
    def get_permissions(self):
        if self.action in ["retrieve", "create", "partial_update"]:
            return [IsAuthenticated()]
        
        return [AllowAny()]

    def retrieve(self, request, pk=None):
        """
        Retrieve a specific shipment by ID with order items.
        GET /api/shipment/{id}
        """
        shipment = get_object_or_404(ShipmentModel, id=pk)
        serializer = ShipmentSerializer(shipment)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Create a new shipment for an order with order items.
        POST /api/shipment
        
        Required fields:
        {
            "orderId": "BDNX#0001",
            "shippingVendorId": 1,
            "orderItemIds": ["uuid1", "uuid2"],  // At least 1 order item required
            "trackingNumber": "ABC123456",  // Optional
            "earliestDeliveryDate": "2025-10-15",  // Optional (YYYY-MM-DD)
            "latestDeliveryDate": "2025-10-17"  // Optional (YYYY-MM-DD)
        }
        
        Note:
        - All new shipments are automatically created with status "pending"
        - Use the PATCH endpoint to update the shipment status
        
        Validations:
        - Order must exist
        - All order items must belong to the specified order
        - Order items must not already be assigned to another shipment
        - Shipping vendor must exist and be active
        - At least 1 order item is required
        """
        serializer = CreateShipmentSerializer(data=request.data)
        
        if serializer.is_valid():
            shipment = serializer.save()
            
            response_serializer = ShipmentSerializer(shipment)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return HttpResponseBadRequest(serializer.errors)
    
    def partial_update(self, request, pk=None):
        """
        Partially update a shipment (PATCH).
        PATCH /api/shipment/{id}
        
        Updatable fields:
        {
            "status": "in_transit",  // Optional - Valid statuses: pending, preparing, shipped, in_transit, out_for_delivery, delivered, failed_delivery, cancelled
            "earliestDeliveryDate": "2025-10-16",  // Optional (YYYY-MM-DD)
            "latestDeliveryDate": "2025-10-18",  // Optional (YYYY-MM-DD)
            "deliveredAt": "2025-10-16T14:30:00Z"  // Optional (ISO datetime) - automatically set when status becomes 'delivered'
        }
        
        Note: 
        - updatedAt is automatically updated on every save
        - deliveredAt is automatically set to current time when status is changed to 'delivered' (if not already set)
        """
        shipment = get_object_or_404(ShipmentModel, id=pk)
        serializer = UpdateShipmentSerializer(shipment, data=request.data, partial=True)
        
        if serializer.is_valid():
            updated_shipment = serializer.save()
            
            response_serializer = ShipmentSerializer(updated_shipment)
            return Response(response_serializer.data)
        
        return HttpResponseBadRequest(serializer.errors)
