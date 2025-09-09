from decimal import Decimal, ROUND_HALF_UP
from typing import Union, Optional
from django.db import models


class CurrencyService:
    """
    Service for handling currency conversions.
    Centralizes currency logic away from models.
    All prices are rounded to whole numbers for simplicity.
    """
    
    @classmethod
    def convert_from_aud(cls, amount: Union[float, Decimal, str], currency_code: str) -> Decimal:
        """
        Convert an amount from AUD to the specified currency.
        Returns the original amount if currency not found or is AUD.
        Rounds to whole numbers using ROUND_HALF_UP.
        
        Args:
            amount: Amount in AUD to convert
            currency_code: Target currency code (e.g., 'USD', 'EUR')
            
        Returns:
            Decimal: Converted amount, rounded to whole number
        """
        if not currency_code or currency_code.upper() == 'AUD':
            return Decimal(str(amount)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            
        try:
            # Import here to avoid circular imports
            from base.models.currency_rate_model import CurrencyRateModel
            
            rate_obj = CurrencyRateModel.objects.get(currency_code=currency_code.upper())
            amount_decimal = Decimal(str(amount))
            converted = amount_decimal * rate_obj.rate
            
            # Round to whole number
            return converted.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        except Exception:  # Catch all exceptions including DoesNotExist, ValueError, TypeError
            return Decimal(str(amount)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)  # Return original amount as fallback
    
    @classmethod
    def convert_to_aud(cls, amount: Union[float, Decimal, str], currency_code: str) -> Decimal:
        """
        Convert an amount from the specified currency to AUD.
        Returns the original amount if currency not found or is AUD.
        Rounds to whole numbers using ROUND_HALF_UP.
        
        Args:
            amount: Amount in the specified currency to convert
            currency_code: Source currency code (e.g., 'USD', 'EUR')
            
        Returns:
            Decimal: Converted amount in AUD, rounded to whole number
        """
        if not currency_code or currency_code.upper() == 'AUD':
            return Decimal(str(amount)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            
        try:
            # Import here to avoid circular imports
            from base.models.currency_rate_model import CurrencyRateModel
            
            rate_obj = CurrencyRateModel.objects.get(currency_code=currency_code.upper())
            if rate_obj.rate > 0:
                amount_decimal = Decimal(str(amount))
                converted = amount_decimal / rate_obj.rate
                # Round to whole number
                return converted.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            return Decimal(str(amount)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        except Exception:  # Catch all exceptions including DoesNotExist, ValueError, TypeError, ZeroDivisionError
            return Decimal(str(amount)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)  # Return original amount as fallback
    
    @classmethod
    def get_rate(cls, currency_code: str) -> Optional[Decimal]:
        """
        Get the exchange rate for a currency from AUD.
        
        Args:
            currency_code: Currency code to get rate for
            
        Returns:
            Decimal: Exchange rate, or None if not found
        """
        if not currency_code or currency_code.upper() == 'AUD':
            return Decimal('1.0')
            
        try:
            from base.models.currency_rate_model import CurrencyRateModel
            rate_obj = CurrencyRateModel.objects.get(currency_code=currency_code.upper())
            return rate_obj.rate
        except Exception:  # Catch all exceptions including DoesNotExist
            return None
