import bcrypt
from django.conf import settings
from django.contrib.auth.hashers import BasePasswordHasher

class BCryptPepperHasher(BasePasswordHasher):
    algorithm = "bcrypt_peppered"

    def salt(self):
        return bcrypt.gensalt().decode("utf-8")

    def encode(self, password, salt):
        peppered = (password + settings.PEPPER).encode("utf-8")
        hashed = bcrypt.hashpw(peppered, salt.encode("utf-8"))
        return f"{self.algorithm}${hashed.decode("utf-8")}"

    def verify(self, password, encoded):
        algorithm, hashed = encoded.split("$", 1)
        if algorithm != self.algorithm:
            return False
        peppered = (password + settings.PEPPER).encode("utf-8")
        return bcrypt.checkpw(peppered, hashed.encode("utf-8"))

    def safe_summary(self, encoded):
        algorithm, hashed = encoded.split("$", 1)
        return {"algorithm": algorithm, "hash": hashed[:6] + "..."}