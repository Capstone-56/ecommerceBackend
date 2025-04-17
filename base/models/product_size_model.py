from django.db import models
import uuid
from .product_model import productModel

class productSizeModel(models.Model):
    ID = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    PRODUCT_ID = models.ForeignKey(ProductModel, on_delete=models.CASCADE, db_column='PRODUCTID')
    SIZE = models.CharField(max_length=7)
    PRICE = models.FloatField()

    def __str__(self):
        return f"{self.PRODUCT_ID} - {self.SIZE} - {self.PRICE}"

    class Meta:
        db_table = "product_sizes"
