from django.db import models
from .product_model import ProductModel
from .category_model import CategoryModel

class ProductCategoryModel(models.Model):
    id = models.AutoField(
        primary_key=True,
        editable=False
    )
    product = models.ForeignKey(
        ProductModel,
        on_delete=models.CASCADE,
        db_column="productId",
        related_name="category_links"
    )
    category = models.ForeignKey(
        CategoryModel,
        to_field="internalName",
        on_delete=models.CASCADE,
        db_column="categoryId",
        related_name="product_links"
    )

    class Meta:
        db_table = "productCategory"
        unique_together = (("product", "category"),)

    def __str__(self):
        return f"Product {self.product.name} - Category {self.category.name}"