from django.db import models
import uuid

class AddressModel(models.Model):
    """
    Stores individual address records for reuse and snapshots.
    This table can only add new records, no record can be deleted or modified
    """
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    addressLine = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    postcode = models.CharField(max_length=10)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)

    class Meta:
        db_table = "address"

    def __str__(self):
        return f"{self.addressLine}, {self.city}, {self.state}, {self.country}"
