import uuid

from django.db import models

from .user_model import UserModel
from .product_item_model import ProductItemModel

class ShoppingCartItemModel(models.Model):
  """
  Model that represents a product item that's been added 
  to cart by an authenticated user
  """
  id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
  user = models.ForeignKey(UserModel, on_delete=models.CASCADE, db_column="userId")
  productItem = models.ForeignKey(ProductItemModel, on_delete=models.CASCADE, db_column="productItemId")
  quantity = models.IntegerField(default=1)

  class Meta:
    db_table = "shoppingCartItem"
    unique_together = [("productItem", "user")]
