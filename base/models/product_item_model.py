from django.db import models

import uuid
from .product_model import ProductModel

class ProductItemModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(ProductModel, on_delete=models.CASCADE, db_column="productId", related_name="items")
    sku = models.CharField(max_length=255)
    stock = models.IntegerField()


    class Meta:
        db_table = "productItem"
