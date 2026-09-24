import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "neuromed_v2.settings")

# Channels routing (live transcript streaming) plugs in here once the
# visits app's consumer is ported from v1's myApp/consumers.py.
django_asgi_app = get_asgi_application()

application = django_asgi_app
