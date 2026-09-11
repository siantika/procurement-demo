"""
WSGI config for config project.

It exposes the WSGI callable as the module-level ``application`` variable.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.demo")

application = get_wsgi_application()
