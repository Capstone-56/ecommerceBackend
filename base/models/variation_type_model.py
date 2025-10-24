from django.db import models
import uuid
from .category_model import CategoryModel

class VariationTypeModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    categories = models.ManyToManyField(
        CategoryModel, 
        related_name="variation_types",
        blank=True
    )

    class Meta:
        db_table = "variationType"
