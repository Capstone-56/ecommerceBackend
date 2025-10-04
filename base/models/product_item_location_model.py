import uuid

from django.db import models
from django.db.models import CheckConstraint, Q
from django.core.validators import MaxValueValidator
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from .product_item_model import ProductItemModel
from .location_model import LocationModel
from .product_location_model import ProductLocationModel

class ProductItemLocationModel(models.Model):
    """
    Model to store location-specific pricing and discounts for product items.
    Combines base price from ProductLocation with variant-specific discounts.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    productItem = models.ForeignKey(ProductItemModel, on_delete=models.CASCADE, db_column="productItemId", related_name="locationPrices")
    location = models.ForeignKey(LocationModel, on_delete=models.CASCADE, db_column="locationId", related_name="productItems")
    discount = models.FloatField(validators=[MaxValueValidator(100.0)])
    startDate = models.DateTimeField(null=True, blank=True, db_column="startDate")
    endDate = models.DateTimeField(null=True, blank=True, db_column="endDate")


    @property
    def base_price(self):
        """
        Get the base price from ProductLocation for this product in this location.
        Returns None if ProductLocation doesn't exist.
        """
        try:
            product_location = ProductLocationModel.objects.get(
                product=self.productItem.product,
                location=self.location
            )
            return product_location.price
        except ObjectDoesNotExist:
            return None


    @property
    def effective_discount(self):
        """
        Get the current effective discount percentage.
        Returns 0 if discount is not active (outside date range).
        """
        now = timezone.now()

        if self.startDate and now < self.startDate:
            return 0.0  # Discount hasn't started yet
        
        if self.endDate and now > self.endDate:
            return 0.0  # Discount has expired
        
        return self.discount
    

    @property
    def final_price(self):
        """
        Calculate the final price after applying discount to base price.
        Formula: base_price * (1 - discount/100)
        Returns None if base_price doesn't exist.
        """
        base = self.base_price
        if base is None:
            return None
        
        discount_percentage = self.effective_discount
        discount_multiplier = 1 - (discount_percentage / 100)
        return base * discount_multiplier


    @property
    def discount_amount(self):
        """
        Calculate the absolute discount amount in currency.
        Returns None if base_price doesn't exist.
        """
        base = self.base_price
        if base is None:
            return None
        
        discount_percentage = self.effective_discount
        return base * (discount_percentage / 100)


    def save(self, *args, **kwargs):
        self.full_clean()  # run validators
        super().save(*args, **kwargs)


    class Meta:
        db_table = "productItemLocation"
        unique_together = [("productItem", "location")]
        constraints = [
            CheckConstraint(
                check=Q(discount__lte=100.0),
                name="discount_max_100"
            )
        ]

