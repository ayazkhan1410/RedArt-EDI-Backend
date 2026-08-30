from django.db import models


class Gender(models.TextChoices):
    MALE = "M", "Male"
    FEMALE = "F", "Female"
    UNKNOWN = "U", "Unknown"
