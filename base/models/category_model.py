import re
from django.db import models
from django.core.exceptions import ValidationError
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
        # Only generate internalName for new instances
        if not self.pk:  # New instance
            # Replace whitespace with hyphens and lowercase:
            # "Men Shirts" → "men-shirts"
            stripped = re.sub(r"\s+", "-", self.name)
            generated_internal_name = stripped.lower()
            
            # Check if the internalName already exists
            if CategoryModel.objects.filter(internalName=generated_internal_name).exists():
                raise ValidationError(
                    f"A category with the name '{self.name}' already exists (internal name: '{generated_internal_name}')."
                )
            
            self.internalName = generated_internal_name
        
        # For updates, internalName remains unchanged, just update other fields
        super().save(*args, **kwargs)

    class Meta:
        db_table = "category"
    
    class MPTTMeta:
        parent_attr = "parentCategory"
