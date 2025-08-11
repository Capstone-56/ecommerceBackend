import bcrypt
from django.conf import settings
from django.contrib.auth.hashers import BasePasswordHasher

class BCryptPepperHasher(BasePasswordHasher):
    """
    Password hasher that combines bcrypt with an application‐wide pepper.

    This hasher generates a salt via bcrypt, appends a secret pepper
    from settings to the raw password, and then hashes the result.
    On verification, it re-applies the same pepper and uses bcrypt to check.
    """
    algorithm = "bcrypt_peppered"

    def salt(self):
        """
       Generate a new bcrypt salt.

       Returns: A UTF-8–decoded bcrypt salt string
       """
        # returns a bytes object, then decode to string for storage
        return bcrypt.gensalt().decode("utf-8")


    def encode(self, password, salt):
        """
        Hash the password with the given salt and the application pepper.

        Args:
            password (string): The plaintext password to hash.
            salt (string): The bcrypt salt previously generated.

        Returns: The final stored string, in format "bcrypt_peppered$<hash>"
        """
        # Combine raw password + secret pepper, then encode to bytes
        peppered = (password + settings.PEPPER).encode("utf-8")

        # Perform bcrypt hashing using the provided salt
        hashed = bcrypt.hashpw(peppered, salt.encode("utf-8"))

        # Prefix with algorithm name so Django knows which hasher to use
        return f"{self.algorithm}${hashed.decode('utf-8')}"


    def verify(self, password, encoded):
        """
        Check a plaintext password against the stored hash.

        Args:
           password (string): The plaintext password to verify.
           encoded (string): The stored hash string from the database.

        Returns: True if the password matches, False otherwise.
        """
        # Split into algorithm identifier and raw bcrypt hash
        algorithm, hashed = encoded.split("$", 1)

        # Reject if the stored algorithm doesn't match this class
        if algorithm != self.algorithm:
            return False

        # Re-apply pepper and check against stored bcrypt hash
        peppered = (password + settings.PEPPER).encode("utf-8")
        return bcrypt.checkpw(peppered, hashed.encode("utf-8"))
