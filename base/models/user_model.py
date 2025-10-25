from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.hashers import make_password
from django.db import models
import uuid
from base.enums import ROLE
from base.managers import UserManager

class UserModel(AbstractBaseUser, PermissionsMixin):
    """
    is_staff and is_active is Django naming convention, DO NOT OVERWRITE
    """
    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    username = models.CharField(max_length=255, unique=True)
    email = models.EmailField(max_length=255, unique=True)
    firstName = models.CharField(max_length=255)
    lastName = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(
        max_length=10,
        choices=[(role.value, role.name.title()) for role in ROLE],
        default=ROLE.CUSTOMER.value,
    )
    refreshToken = models.CharField(max_length=255, unique=True, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "firstName", "lastName"]

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def __str__(self):
        return f"{self.username}"

    class Meta:
        db_table = "user"  # Overwrites the default table name
