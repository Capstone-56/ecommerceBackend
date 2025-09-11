"""
Address creation service for handling shipping address data.
"""
import logging
from api.serializers import AddressSerializer

logger = logging.getLogger(__name__)


class AddressService:
    """Service for creating addresses from shipping metadata."""
    
    @staticmethod
    def create_from_shipping_metadata(metadata):
        """
        Creates an address from shipping metadata stored in PaymentIntent.
        
        Args:
            metadata (dict): PaymentIntent metadata containing shipping information
            
        Returns:
            str: Address ID if created successfully, None if failed
        """
        try:
            # Combine line1 and line2 for full address
            line1 = metadata.get("shipping_line1", "")
            line2 = metadata.get("shipping_line2", "")
            
            if line2:
                full_address = f"{line2}, {line1}"  # Unit/Apt first, then street
            else:
                full_address = line1
            
            address_data = {
                "addressLine": full_address,
                "city": metadata.get("shipping_city", ""),
                "postcode": metadata.get("shipping_postal_code", ""),
                "state": metadata.get("shipping_state", ""),
                "country": metadata.get("shipping_country", ""),
            }
            
            serializer = AddressSerializer(data=address_data)
            if serializer.is_valid():
                address = serializer.save()
                logger.debug(f"Created address {address.id} from shipping metadata")
                return str(address.id)
            else:
                logger.error(f"Address creation validation failed: {serializer.errors}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create address from shipping metadata: {e}", exc_info=True)
            return None