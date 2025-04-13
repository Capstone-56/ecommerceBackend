from django.db import models
import uuid

class CategoryModel(models.Model):
    ID = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    NAME = models.CharField(max_length=255)
    DESCRIPTION = models.CharField(max_length=255)
    PARENT_CATEGORY_ID = models.UUIDField(null=True, blank=True)

    def __str__(self):
        return self.NAME

    class Meta:
        db_table = "category"
