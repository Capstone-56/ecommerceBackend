from django.db import models
import uuid

class CategoryModel(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    parentCategoryId = models.UUIDField(null=True, blank=True)

    def __str__(self):
        return self.name
    
    def get_all_subcategories(self):
        """
        This method is used to retrieve the IDs of all
        subcategories, including nested subcategories, for a given category.
        """
        subcategories = CategoryModel.objects.filter(parentCategoryId=self.id)
        subcategory_ids = [self.id]
        for subcategory in subcategories:
            subcategory_ids.extend(subcategory.get_all_subcategories())
        return subcategory_ids

    class Meta:
        db_table = "category"