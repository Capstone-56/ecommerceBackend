from django.db import models
import uuid
from .variation_type_model import VariationType

class Variant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    value = models.CharField(max_length=255)
    variationTypeId = models.ForeignKey(VariationType, on_delete=models.CASCADE, db_column="variationTypeId")

    class Meta:
        db_table = "variant"