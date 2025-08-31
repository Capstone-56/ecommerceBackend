from django.db import models
from django.utils import timezone
from django.conf import settings


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

    @classmethod
    def get_rate_to_currency(cls, currency_code):
        """
        Get the current exchange rate from AUD to the specified currency.
        Returns None if currency not found.
        """
        try:
            rate_obj = cls.objects.get(currency_code=currency_code.upper())
            return rate_obj.rate
        except cls.DoesNotExist:
            return None

    @classmethod
    def convert_from_aud(cls, amount, currency_code):
        """
        Convert an amount from AUD to the specified currency.
        Returns None if currency not found.
        """
        rate = cls.get_rate_to_currency(currency_code)
        if rate is not None:
            return amount * rate
        return None

    @classmethod
    def convert_to_aud(cls, amount, currency_code):
        """
        Convert an amount from the specified currency to AUD.
        Returns None if currency not found.
        """
        rate = cls.get_rate_to_currency(currency_code)
        if rate is not None and rate > 0:
            return amount / rate
        return None

    def save(self, *args, **kwargs):
        """Override save to ensure currency code is uppercase."""
        self.currency_code = self.currency_code.upper()
        super().save(*args, **kwargs)
