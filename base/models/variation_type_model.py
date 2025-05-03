from django.db import models
import uuid
from .category_model import CategoryModel

class VariationTypeModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    category = models.ForeignKey(CategoryModel, on_delete=models.CASCADE, db_column="categoryID", null=True, blank=True)

    class Meta:
        db_table = "variationType"
