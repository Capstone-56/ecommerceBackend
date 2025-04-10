from django.db import models
import uuid

class UserModel(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    username = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    password = models.BinaryField(editable=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "user"  # Overwrites the default table name
