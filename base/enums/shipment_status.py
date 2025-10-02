from enum import Enum

class SHIPMENT_STATUS(Enum):
    """
    Statuses for ShipmentModel
    """
    PENDING = "pending"
    PREPARING = "preparing"
    SHIPPED = "shipped"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED_DELIVERY = "failed_delivery"
    CANCELLED = "cancelled"