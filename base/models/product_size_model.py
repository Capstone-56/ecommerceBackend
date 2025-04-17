from django.db import models
import uuid
from .product_model import ProductModel

class ProductSizeModel(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    productId = models.ForeignKey(ProductModel, on_delete=models.CASCADE, db_column="productId")
    size = models.CharField(max_length=7)
    price = models.FloatField()

    def __str__(self):
        return self.id

    class Meta:
        db_table = "productSize"