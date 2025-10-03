from django.db import models

class LocationModel(models.Model):
    country_code = models.CharField(max_length=2, primary_key=True)  # e.g. "AU", "US"
    country_name = models.CharField(max_length=100)
    currency_code = models.CharField(max_length=3, null=True, blank=True)  # USD, AUD, GBP, EUR

    def __str__(self):
        return self.country_name
    
    class Meta:
        db_table = "location"