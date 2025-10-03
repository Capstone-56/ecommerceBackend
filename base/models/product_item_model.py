from django.db import models
from django.contrib.postgres.fields import ArrayField
import uuid
from .product_model import ProductModel

class ProductItemModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(ProductModel, on_delete=models.CASCADE, db_column="productId", related_name="items")
    sku = models.CharField(max_length=255)
    stock = models.IntegerField()
    imageUrls = ArrayField(models.CharField(max_length=1000), blank=True)

    class Meta:
        db_table = "productItem"
    
    @property
    def prices(self):
        """
        Returns location-based pricing as dict format:
        {"AU": {"amount": 19.99, "currency": "AUD"}, "US": {"amount": 14.99, "currency": "USD"}}
        """
        from .product_item_price_model import ProductItemPriceModel
        price_objects = self.country_prices.all().select_related('location')
        return {
            price_obj.location.country_code.upper(): {
                "amount": price_obj.price,
                "currency": price_obj.location.currency_code
            }
            for price_obj in price_objects
        }
    
    @property  
    def price(self):
        """
        Backward compatibility - returns AU price only.
        Returns None if no AU price exists.
        """
        au_price = self.country_prices.filter(location__country_code='au').first()
        return au_price.price if au_price else None
    
    def get_price_for_location(self, location_code):
        """
        Get price for specific location.
        Args:
            location_code (str): Country code (e.g., 'au', 'us')
        Returns:
            float: Price for location or None if not available
        """
        price_obj = self.country_prices.filter(location__country_code=location_code.lower()).first()
        return price_obj.price if price_obj else None
