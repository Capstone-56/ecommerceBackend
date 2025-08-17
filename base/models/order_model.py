import uuid

from django.db import models

from .user_model import UserModel
from .address_model import AddressModel
from .shipping_vendor_model import ShippingVendorModel

from base.enums import ORDER_STATUS

class OrderModel(models.Model):
    """
    Model that represents an order
    """
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE, db_column="userId")
    address = models.ForeignKey(AddressModel, on_delete=models.CASCADE, db_column="addressId")
    shippingVendor = models.ForeignKey(ShippingVendorModel, on_delete=models.CASCADE, db_column="shippingVendorId")
    totalPrice = models.FloatField()
    status = models.CharField(
        max_length=20,
        choices=[(status.value, status.name.title()) for status in ORDER_STATUS],
        default=ORDER_STATUS.PENDING.value
    )

    class Meta:
        db_table = "order"
