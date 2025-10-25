from enum import Enum

class ROLE(Enum):
    """
    Roles for UserModel
    """
    CUSTOMER = "customer"
    SELLER = "seller"
    MANAGER = "manager"
    ADMIN = "admin"
