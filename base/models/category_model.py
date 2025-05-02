import re
from django.db import models
from mptt.models import MPTTModel, TreeForeignKey

class CategoryModel(MPTTModel):
    internalName = models.CharField(
        max_length=255,
        editable=False,
        unique=True,
        primary_key=True
    )
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    parentCategory = TreeForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="internalName",
        db_column="parentCategory",
        related_name="children"     # reverse relation: category.children.all()
    )

    def save(self, *args, **kwargs):
        # Remove all whitespace and lowercase:
        # "My Category Name" → "mycategoryname"
        stripped = re.sub(r"\s+", "", self.name)
        self.internalName = stripped.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "category"
    
    class MPTTMeta:
        parent_attr = 'parentCategory'
        order_insertion_by = ['name']