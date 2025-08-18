from django.db import models

class LocationModel(models.Model):
    country_code = models.CharField(max_length=2, primary_key=True)  # e.g. "US", "GB"
    country_name = models.CharField(max_length=100)
    # Optionally add city, region, etc.

    def __str__(self):
        return self.country_name
    
    class Meta:
        db_table = "location"