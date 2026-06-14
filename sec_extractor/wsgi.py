"""WSGI config for sec_extractor."""
import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sec_extractor.settings")

application = get_wsgi_application()
