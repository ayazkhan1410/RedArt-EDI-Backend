from django.db import models


class Environment(models.TextChoices):
    TEST = "TEST", "Test"
    PRODUCTION = "PRODUCTION", "Production"
