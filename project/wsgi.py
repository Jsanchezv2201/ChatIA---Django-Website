"""
WSGI config for project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

# En un entorno sin estado como Vercel, la base de datos SQLite puede no persistir.
# Este bloque se asegura de que las migraciones se apliquen en cada despliegue nuevo
# o reinicio del entorno, creando las tablas necesarias si no existen.
# Se usa un archivo temporal como bandera para evitar ejecuciones múltiples.
if os.environ.get('VERCEL') == '1':
    # La ruta a la bandera debe ser en un directorio escribible, como /tmp
    flag_path = '/tmp/migrations_run.flag'
    if not os.path.exists(flag_path):
        try:
            call_command('migrate', interactive=False)
            # Crear la bandera para indicar que las migraciones se ejecutaron
            with open(flag_path, 'w') as f:
                f.write('done')
        except Exception as e:
            # Es importante registrar cualquier error para depuración
            print(f"Error running migrations: {e}")


application = get_wsgi_application()
