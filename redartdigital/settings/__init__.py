# Default to local settings when DJANGO_SETTINGS_MODULE is redartdigital.settings
from redartdigital.settings.local import *  # noqa: F401, F403
from redartdigital.settings.base import env  # noqa: F401
