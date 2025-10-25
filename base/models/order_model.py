import uuid

from django.db import models
from django.core.exceptions import ValidationError

from .user_model import UserModel
from .guest_user_model import GuestUserModel
from .address_model import AddressModel

from base.enums import ORDER_STATUS

class OrderModel(models.Model):
    """
    Model that represents an order for both authenticated and guest users
    """
    id = models.CharField(max_length=20, primary_key=True, editable=False)
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
        if not self.id:
            last_obj = self.__class__.objects.order_by('createdAt').last()
            if last_obj is None:
                last_number = 0
            else:
                last_number_str = ''.join(filter(str.isdigit, last_obj.id or '0'))
                last_number = int(last_number_str) if last_number_str else 0

            # Format with at least 4 digits, will expand if number > 9999.
            self.id = f'BDNX#{last_number + 1:04d}'
        super().save(*args, **kwargs)
    

    class Meta:
        db_table = "order"
