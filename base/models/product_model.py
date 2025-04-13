from django.db import models
from django.contrib.postgres.fields import ArrayField
import uuid

"""
A model to generate the product table in a PostgreSQL database.
Columns:
    ID          UUID to store each product uniquely.
    NAME        Name of the product to sell.
    DESCRIPTION The associated description of what the product is.
    IMAGES      Image urls to display on frontend.
"""
class ProductModel(models.Model):
    ID = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    NAME = models.CharField(max_length=255)
    DESCRIPTION = models.CharField(max_length=255)
    IMAGES = ArrayField(models.CharField(max_length=1000), blank=True)

    def __str__(self):
        return self.NAME

    class Meta:
        db_table = "product"  # Overwrites the default table name
