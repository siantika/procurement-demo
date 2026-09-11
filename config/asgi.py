"""
ASGI config for config project.

It exposes the ASGI callable as the module-level ``application`` variable.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.demo")

application = get_asgi_application()
