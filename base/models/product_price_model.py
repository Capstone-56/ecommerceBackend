from django.db import models
import uuid
from .product_model import ProductModel

class ProductPriceModel(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    productId = models.OneToOneField(ProductModel, on_delete=models.CASCADE, db_column="productId", related_name="price")
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Product: {self.productId}, Price: {self.price}"

    class Meta:
        db_table = "productPrice"