from django.db import models

from apps.core.models import BaseModel
from apps.patient.choices import Gender


class Patient(BaseModel):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, blank=True, null=True)
    date_of_birth = models.DateField()
    gender = models.CharField(
        max_length=1,
        choices=Gender.choices,
        null=True,
        blank=True,
    )
    medicaid_member_id = models.CharField(max_length=255, unique=True)
    county = models.CharField(max_length=255)
    address_line_1 = models.CharField(max_length=500, blank=True, null=True)
    address_line_2 = models.CharField(max_length=500, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=2, blank=True, null=True)
    zip = models.CharField(max_length=20, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Patient"
        verbose_name_plural = "Patients"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def has_837p_demographics(self):
        """Minimum subscriber demographics for a basic 837P NM1/N3/N4/DMG path."""
        return bool(
            self.gender
            and self.address_line_1
            and self.city
            and self.state
            and self.zip
        )
