from django.db import models
import uuid
from .product_model import ProductModel

class ProductColourModel(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    productId = models.ForeignKey(ProductModel, on_delete=models.CASCADE, db_column="productId")
    colour = models.CharField(max_length=50)

    def __str__(self):
        return f"Product: {self.productId}, Colour: {self.colour}"

    class Meta:
        db_table = "productColour"