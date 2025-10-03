import uuid
from django.db import models
from .product_item_model import ProductItemModel
from .location_model import LocationModel

class ProductItemPriceModel(models.Model):
    """
    Stores location-specific pricing for product items.
    Each product item can have different prices in different locations/currencies.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    productItem = models.ForeignKey(
        ProductItemModel, 
        on_delete=models.CASCADE, 
        db_column="productItemId",
        related_name="country_prices"
    )
    location = models.ForeignKey(
        LocationModel, 
        on_delete=models.CASCADE, 
        db_column="locationId"
    )
    price = models.FloatField()
    
    class Meta:
        db_table = "productItemPrice"
        unique_together = [("productItem", "location")]
    
    def __str__(self):
        return f"{self.productItem.sku} - {self.location.country_code}: {self.price}"