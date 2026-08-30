from django.db import models


class CountyType(models.TextChoices):
    STANDARD = "STANDARD", "Standard"
    DESIGNATED_RURAL = "DESIGNATED_RURAL", "Designated rural"
