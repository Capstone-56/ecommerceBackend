from django.db import models
import uuid
from .product_model import productModel
from .category_model import categoryModel

class productCategoryModel(models.Model):
    ID = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    PRODUCT_ID = models.ForeignKey(ProductModel, on_delete=models.CASCADE, db_column='PRODUCTID')
    CATEGORY_ID = models.ForeignKey(CategoryModel, on_delete=models.CASCADE, db_column='CATEGORYID')

    def __str__(self):
        return f"{self.PRODUCT_ID} - {self.CATEGORY_ID}"

    class Meta:
        db_table = "product_category"
