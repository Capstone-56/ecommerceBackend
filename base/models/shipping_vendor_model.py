from django.db import models

class ShippingVendorModel(models.Model):
    """
    Model for shipping vendors (AusPost, FedEx, etc.)
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=127)
    logoUrl = models.TextField()
    isActive = models.BooleanField(default=True)

    class Meta:
        db_table = "shippingVendor"
