from django.db import models
from django.contrib.postgres.fields import ArrayField
import uuid

from .category_model import CategoryModel

class ProductModel(models.Model):
    """
    A model to generate the product table in a PostgreSQL database.
    Columns:
        id          UUID to store each product uniquely.
        name        Name of the product to sell.
        description The associated description of what the product is.
        images      Image urls to display on frontend.
        featured    Boolean flag indicating whether the product is featured.
        avgRating   Average rating of the product.
    """
    id          = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    name        = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    images      = ArrayField(models.CharField(max_length=1000), blank=True)
    featured    = models.BooleanField(default=False)
    avgRating   = models.FloatField(null=True, blank=True, db_column="avgRating")
    category    = models.ForeignKey(CategoryModel, to_field="internalName", db_column="categoryId", related_name="category", on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "product"  # Overwrites the default table name
