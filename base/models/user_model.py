from django.db import models

class UserModel(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name
