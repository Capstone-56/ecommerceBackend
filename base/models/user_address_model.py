from django.db import models
import uuid
from . import UserModel, AddressModel

class UserAddressModel(models.Model):
    """
    Links Users to AddressModel entries, marking defaults.
    """
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    user = models.ForeignKey(
        UserModel,
        on_delete=models.CASCADE,
        related_name="user_addresses",
        db_column="userId"
    )
    address = models.ForeignKey(
        AddressModel,
        on_delete=models.CASCADE,
        related_name="address_users",
        db_column="addressId"
    )
    isDefault = models.BooleanField(default=False)

    class Meta:
        db_table = "userAddress"
        unique_together = [("user", "address")]

    def __str__(self):
        return f"{self.user.username} -> {self.address} (default={self.isDefault})"
