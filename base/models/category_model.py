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
        # Replace whitespace with hyphens and lowercase:
        # "Men Shirts" → "men-shirts"
        stripped = re.sub(r"\s+", "-", self.name)
        generated_internal_name = stripped.lower()
        
        old_internal_name = self.pk  # Store the old primary key (internalName)
        
        if old_internal_name:  # This is an update
            # Check if the internalName will change
            if old_internal_name != generated_internal_name:
                # Check if the new internalName conflicts with another category
                if CategoryModel.objects.filter(internalName=generated_internal_name).exists():
                    raise ValidationError(
                        f"A category with the name '{self.name}' already exists (internal name: '{generated_internal_name}')."
                    )
                
                # Update all children to point to the new internalName
                CategoryModel.objects.filter(parentCategory=old_internal_name).update(
                    parentCategory=generated_internal_name
                )
                
                # Delete the old record
                CategoryModel.objects.filter(internalName=old_internal_name).delete()
                
                # Force insert to create a new record with the new internalName
                self.internalName = generated_internal_name
                kwargs['force_insert'] = True
                super().save(*args, **kwargs)
                
                # Rebuild the MPTT tree structure to fix breadcrumbs and hierarchy
                CategoryModel.objects.rebuild()
            else:
                # No name change, just update normally
                self.internalName = generated_internal_name
                super().save(*args, **kwargs)
        else:  # New instance
            if CategoryModel.objects.filter(internalName=generated_internal_name).exists():
                raise ValidationError(
                    f"A category with the name '{self.name}' already exists (internal name: '{generated_internal_name}')."
                )
            self.internalName = generated_internal_name
            super().save(*args, **kwargs)

    class Meta:
        db_table = "category"
    
    class MPTTMeta:
        parent_attr = "parentCategory"
