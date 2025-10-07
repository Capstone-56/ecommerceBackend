import uuid

from django.db import models
from django.db.models import CheckConstraint, Q
from django.core.validators import MinValueValidator

from .product_model import ProductModel
from .location_model import LocationModel

class ProductLocationModel(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    product = models.ForeignKey(ProductModel, on_delete=models.CASCADE, db_column="productId", related_name="locations")
    location = models.ForeignKey(LocationModel, on_delete=models.CASCADE, db_column="locationId", related_name="products")
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    price = models.FloatField(validators=[MinValueValidator(0.0)])

    @property
    def currency_code(self):
        """Get the currency code from the associated location"""
        return self.location.currency_code

    def save(self, *args, **kwargs):
        self.full_clean()  # run validators
        super().save(*args, **kwargs)


    class Meta:
        db_table = "productLocation"
        unique_together = ("product", "location")
        constraints = [
            CheckConstraint(
                check=Q(price__gte=0.0),
                name="price_min_0"
            )
        ]
