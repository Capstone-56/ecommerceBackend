from django.db import models
import uuid
from .product_model import ProductModel
from .category_model import CategoryModel

class ProductCategoryModel(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    productId = models.ForeignKey(ProductModel, on_delete=models.CASCADE, db_column="productId")
    categoryId = models.ForeignKey(CategoryModel, on_delete=models.CASCADE, db_column="categoryId")

    def __str__(self):
        return self.id

    class Meta:
        db_table = "productCategory"