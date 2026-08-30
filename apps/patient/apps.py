from django.apps import AppConfig


class PatientConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.patient"
    label = "patient"
    verbose_name = "Patient"
