from django.db import models
import uuid
from .product_model import ProductModel
from .variant_model import VariantModel

class ProductConfig(models.Model):
    product = models.ForeignKey(ProductModel, on_delete=models.CASCADE, db_column="productId")
    variant = models.ForeignKey(VariantModel, on_delete=models.CASCADE, db_column="variantId")

    class Meta:
        db_table = "productConfig"
        unique_together = (("product", "variant"),)
        