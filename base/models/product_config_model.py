from django.db import models
import uuid
from .product_item_model import ProductItemModel
from .variant_model import VariantModel

class ProductConfigModel(models.Model):
    productItem = models.ForeignKey(ProductItemModel, on_delete=models.CASCADE, db_column="productItemId")
    variant = models.ForeignKey(VariantModel, on_delete=models.CASCADE, db_column="variantId")

    class Meta:
        db_table = "productConfig"
        unique_together = (("productItem", "variant"),)
