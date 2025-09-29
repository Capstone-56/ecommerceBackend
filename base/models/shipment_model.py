import uuid
from django.db import models
from .order_model import OrderModel
from .shipping_vendor_model import ShippingVendorModel
from base.enums import SHIPMENT_STATUS

class ShipmentModel(models.Model):
    """
    Model that represents a shipment containing one or more order items
    """
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)
    
    order = models.ForeignKey(
        OrderModel, 
        on_delete=models.CASCADE, 
        db_column="orderId",
        related_name="shipments"
    )
    shippingVendor = models.ForeignKey(
        ShippingVendorModel, 
        on_delete=models.CASCADE, 
        db_column="shippingVendorId"
    )
    
    trackingNumber = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[(status.value, status.name.title()) for status in SHIPMENT_STATUS],
        default=SHIPMENT_STATUS.PENDING.value
    )
    
    earliestDeliveryDate = models.DateField(null=True, blank=True)
    latestDeliveryDate = models.DateField(null=True, blank=True)
    deliveredAt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "shipment"