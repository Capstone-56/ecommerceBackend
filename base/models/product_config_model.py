from django.db import models
import uuid
from .product_model import ProductModel
from .variant_model import Variant

class ProductConfig(models.Model):
    productId = models.ForeignKey(ProductModel, on_delete=models.CASCADE, db_column="productId")
    variantId = models.ForeignKey(Variant, on_delete=models.CASCADE, db_column="variantId")

    class Meta:
        db_table = "productConfig"
        unique_together = (("productId", "variantId"),)