web: python manage.py collectstatic --noinput && gunicorn neuromed_v2.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 120
