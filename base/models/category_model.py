from django.db import models
import uuid

class CategoryModel(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    parentCategoryId = models.UUIDField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "category"