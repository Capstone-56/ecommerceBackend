from django.db import models
import uuid
from .product_model import ProductModel
from .category_model import CategoryModel

class ProductCategoryModel(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4,
        primary_key=True,
        editable=False,
        unique=True
    )
    productId = models.ForeignKey(
        ProductModel,
        on_delete=models.CASCADE,
        db_column="productId",
        related_name="category_links"
    )
    categoryId = models.ForeignKey(
        CategoryModel,
        to_field="internalName",
        on_delete=models.CASCADE,
        db_column="categoryId",
        related_name="product_links"
    )

    class Meta:
        db_table = "productCategory"
        unique_together = (("productId", "categoryId"),)

    def __str__(self):
        return f"Product {self.productId.name} ↔ Category {self.categoryId.name}"