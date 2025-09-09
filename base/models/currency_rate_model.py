from django.db import models
from django.utils import timezone
from django.conf import settings
from decimal import Decimal


class CurrencyRateModel(models.Model):
    """
    Stores conversion rates from AUD (base currency) to other currencies.
    Rate represents: 1 AUD = rate * target_currency
    """
    currency_code = models.CharField(max_length=3, unique=True)  # e.g. "USD", "EUR", "GBP"
    rate = models.DecimalField(max_digits=15, decimal_places=6)  # Exchange rate from AUD
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "currency_rate"
        indexes = [
            models.Index(fields=['currency_code']),
            models.Index(fields=['last_updated']),
        ]

    def __str__(self):
        return f"AUD/{self.currency_code}: {self.rate}"

    def save(self, *args, **kwargs):
        """Override save to ensure currency code is uppercase."""
        self.currency_code = self.currency_code.upper()
        super().save(*args, **kwargs)
