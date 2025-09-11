import uuid
from django.db import models

class GuestUserModel(models.Model):
    """
    Model to handle anonymous guest users for orders.
    A new guest user is created for each order to maintain anonymity.
    """
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    email = models.EmailField(max_length=255)
    firstName = models.CharField(max_length=255)
    lastName = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    class Meta:
        db_table = "guestUser"
