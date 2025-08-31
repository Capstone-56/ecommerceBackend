from django.db import models

class LocationModel(models.Model):
    country_code = models.CharField(max_length=2, primary_key=True)  # e.g. "US", "GB"
    country_name = models.CharField(max_length=100)
    currency_code = models.CharField(max_length=3, null=True, blank=True)  # e.g. "USD", "GBP", "AUD"
    currency_symbol = models.CharField(max_length=5, null=True, blank=True)  # e.g. "$", "£", "A$"
    # Optionally add city, region, etc.

    def __str__(self):
        return self.country_name
    
    class Meta:
        db_table = "location"