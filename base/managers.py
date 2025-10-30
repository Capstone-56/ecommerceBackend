from django.contrib.auth.models import BaseUserManager

class UserManager(BaseUserManager):
    """
    Custom manager for UserModel that handles user creation.
    Provides methods for creating regular users and superusers.
    is_staff and is_superuser is Django naming convention, DO NOT OVERRIDE
    """
    # Allow this manager to be serialized into migrations
    use_in_migrations = True

    def create_user(self, username, email, password=None, **extra_fields):
        """
        Create a regular user (non-staff, non-superuser).

        Args:
            username (str):    The unique username.
            email (str):       The user's email address.
            password (str):    Raw password (optional; if None, user has no usable password).
            **extra_fields:    Additional model fields (e.g., first_name, last_name).

        Returns:
            UserModel: The created non-staff user.
        """

        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        return self._create_user(username, email, password, **extra_fields)


    # Can potentially be removed if not using Django's superuser semantic
    def create_superuser(self, username, email, password=None, **extra_fields):
        """
        Create a superuser (staff and superuser privileges).

        Args:
            username (string):    The unique username.
            email (string):       The user's email address.
            password (string):    Raw password (should not be None).
            **extra_fields:    Additional model fields.

        Returns:
            UserModel: The created superuser.

        Raises:
            ValueError: If `is_staff` or `is_superuser` are not True.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(username, email, password, **extra_fields)


    def _create_user(self, username, email, password, **extra_fields):
        """
        Internal helper to create and save a UserModel.

        Args:
            username (string): The unique username.
            email (string): The user's email address.
            password (string): Raw password (can be None to create an unusable password).
            **extra_fields: Additional model fields to set on the user.

        Returns:
            UserModel: The newly created user instance.

        Raises:
            ValueError: If no email is provided.
        """
        if not email:
            raise ValueError("The Email must be set")

        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user
