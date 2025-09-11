import uuid

from django.db import models

from .product_item_model import ProductItemModel
from .order_model import OrderModel

class OrderItemModel(models.Model):
    """
    Model that represents a product item in an order
    """
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    order = models.ForeignKey(OrderModel, on_delete=models.CASCADE, db_column="orderId", related_name="items")
    productItem = models.ForeignKey(ProductItemModel, on_delete=models.CASCADE, db_column="productItemId")
    quantity = models.IntegerField(default=1)
    price = models.FloatField()

    class Meta:
        db_table = "orderItem"
