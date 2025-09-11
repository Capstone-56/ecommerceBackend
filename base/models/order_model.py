import uuid

from django.db import models
from django.core.exceptions import ValidationError

from .user_model import UserModel
from .guest_user_model import GuestUserModel
from .address_model import AddressModel
from .shipping_vendor_model import ShippingVendorModel

from base.enums import ORDER_STATUS

class OrderModel(models.Model):
    """
    Model that represents an order for both authenticated and guest users
    """
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    createdAt = models.DateTimeField(auto_now_add=True)

    # Either user OR guest_user must be provided, but not both
    user = models.ForeignKey(
        UserModel, 
        on_delete=models.CASCADE, 
        db_column="userId",
        null=True,
        blank=True,
        related_name="orders"
    )
    guestUser = models.ForeignKey(
        GuestUserModel,
        on_delete=models.CASCADE,
        db_column="guestUserId", 
        null=True,
        blank=True,
        related_name="orders"
    )

    address = models.ForeignKey(AddressModel, on_delete=models.CASCADE, db_column="addressId")
    shippingVendor = models.ForeignKey(ShippingVendorModel, on_delete=models.CASCADE, db_column="shippingVendorId")
    totalPrice = models.FloatField()
    status = models.CharField(
        max_length=20,
        choices=[(status.value, status.name.title()) for status in ORDER_STATUS],
        default=ORDER_STATUS.PENDING.value
    )
    paymentIntentId = models.CharField(max_length=255, null=True, blank=True, db_index=True, unique=True)
    
    def clean(self):
        """Ensure exactly one of user or guestUser is provided"""
        if not self.user and not self.guestUser:
            raise ValidationError("Either user or guestUser must be provided")
        if self.user and self.guestUser:
            raise ValidationError("Cannot have both user and guestUser")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    

    class Meta:
        db_table = "order"
