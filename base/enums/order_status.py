from enum import Enum

class ORDER_STATUS(Enum):
    """
    Statuses for OrderModel
    """
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
