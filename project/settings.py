"""
Configuración central de Django para este proyecto.

Este archivo concentra los ajustes que Django necesita para arrancar la app,
conectar con la base de datos, cargar plantillas, servir estáticos y aplicar
las opciones de seguridad tanto en desarrollo como en producción.

Generado con 'django-admin startproject' usando Django 5.1.7.

Para más información sobre este archivo, consulta
https://docs.djangoproject.com/en/5.1/topics/settings/

Para la lista completa de ajustes y sus valores, consulta
https://docs.djangoproject.com/en/5.1/ref/settings/
"""

import os
from pathlib import Path

# Ruta absoluta a la raíz del proyecto.
# Se usa como punto de partida para localizar la base de datos, estáticos y .env.
BASE_DIR = Path(__file__).resolve().parent.parent


def load_local_env(path):
    """Carga un archivo .env local para definir variables de entorno sin subir secretos al repositorio."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip())


def env_first(*names, default=''):
    """Busca varias variables de entorno y devuelve la primera que tenga contenido útil."""
    for name in names:
        value = os.getenv(name, '').strip()
        if value:
            return value
    return default


load_local_env(BASE_DIR / '.env')


# Ajustes pensados para desarrollo local.
# En producción conviene revisar la lista de despliegue de Django antes de publicar.

# Clave secreta de Django.
# Firma sesiones, tokens CSRF y otras operaciones sensibles; nunca debe publicarse.
SECRET_KEY = env_first('DJANGO_SECRET_KEY', default='django-insecure-2ooa$qfu6t^e$zp6+!eu+3z3a+ko@d+u01lxuzbbw$79)cg!8o')

# Modo depuración.
# Si está activo, Django muestra errores detallados y ayuda durante el desarrollo.
DEBUG = env_first('DJANGO_DEBUG', default='True') == 'True'

# Hosts permitidos para acceder a la aplicación.
# Evita que Django responda a dominios no autorizados. En producción se ajusta con una lista separada por comas.
# DJANGO_ALLOWED_HOSTS=yourusername.pythonanywhere.com,example.com
ALLOWED_HOSTS = [h.strip() for h in env_first('DJANGO_ALLOWED_HOSTS', default='juansv22.pythonanywhere.com,localhost,127.0.0.1,[::1]').split(',') if h.strip()]

# Orígenes de confianza para CSRF.
# Django usa esto para permitir peticiones POST seguras desde dominios concretos.
CSRF_TRUSTED_ORIGINS = [u.strip() for u in env_first('DJANGO_CSRF_TRUSTED_ORIGINS', default='https://juansv22.pythonanywhere.com').split(',') if u.strip()]


# Aplicaciones activas.
# Aquí se registran los módulos de Django y la app propia del proyecto.

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'chatia',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'chatia.context_processors.site_metrics',
            ],
        },
    },
]

WSGI_APPLICATION = 'project.wsgi.application'


# Configuración de base de datos.
# En este proyecto se usa SQLite por simplicidad en local y en pruebas.
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Validadores de contraseñas.
# Django aplica estas reglas cuando se crean o cambian contraseñas de usuario.
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internacionalización y zona horaria.
# Controla el idioma de la interfaz y cómo se muestran/guardan las fechas.
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Europe/Madrid'

USE_I18N = True

USE_TZ = True


# Archivos estáticos.
# Django usa estos ajustes para encontrar CSS, JavaScript e imágenes propios de la aplicación.
# https://docs.djangoproject.com/en/5.1/howto/static-files/

# URL pública con la que se sirven los estáticos.
STATIC_URL = '/static/'
# Carpeta destino de `collectstatic` cuando se prepara un despliegue.
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Carpetas extra donde Django buscará estáticos además de los `static/` de cada app.
STATICFILES_DIRS = [BASE_DIR / 'static']

# Redirección después de iniciar y cerrar sesión.
LOGIN_REDIRECT_URL = 'chatia:home'
LOGOUT_REDIRECT_URL = 'login'

# Configuración del servicio LLM.
# Estas variables permiten cambiar proveedor, modelo y tamaño máximo de respuesta sin tocar el código.
LLM_BASE_URL = env_first('LLM_BASE_URL', default='https://integrate.api.nvidia.com/v1')
LLM_API_KEY = env_first('LLM_API_KEY', 'OPENAI_API_KEY', 'NVIDIA_API_KEY')
LLM_MODEL_1 = env_first('LLM_MODEL_1')
LLM_MODEL_2 = env_first('LLM_MODEL_2')
LLM_MODEL_3 = env_first('LLM_MODEL_3')
LLM_MODEL_4 = env_first('LLM_MODEL_4')
LLM_MODEL = env_first('LLM_MODEL', default=LLM_MODEL_1 or 'meta/llama-3.1-8b-instruct')
LLM_MAX_TOKENS = int(env_first('LLM_MAX_TOKENS', default='1024'))


def llm_model_info(model_value):
    """Construye la ficha visible de un modelo: valor técnico, nombre legible y descripción."""
    preset_info = {
        'meta/llama-3.1-8b-instruct': {
            'label': 'Meta Llama 3.1 8B Instruct',
            'description': 'Equilibrado. Buena opción general para responder con rapidez y calidad razonable.',
        },
        'google/gemma-3n-e2b-it': {
            'label': 'Google Gemma 3n E2B IT',
            'description': 'Ligero y rápido. Bien para respuestas ágiles y pruebas cortas.',
        },
        'meta/llama-4-maverick-17b-128e-instruct': {
            'label': 'Meta Llama 4 Maverick 17B 128E Instruct',
            'description': 'Más potente y exigente. Útil si buscas mayor calidad en razonamiento y redacción.',
        },
        'openai/gpt-oss-120b': {
            'label': 'OpenAI GPT-OSS 120B',
            'description': 'Muy potente. Recomendado si quieres priorizar calidad, aunque puede ser más pesado.',
        },
    }
    info = preset_info.get(model_value)
    if info:
        return {
            'value': model_value,
            'label': info['label'],
            'description': info['description'],
        }
    return {
        'value': model_value,
        'label': model_value,
        'description': 'Modelo configurado en el entorno.',
    }
# Catálogo de modelos disponibles para la interfaz.
# Si hay varios modelos configurados en el entorno, se muestran como opciones al usuario.
LLM_MODEL_CATALOG = [llm_model_info(model) for model in [LLM_MODEL_1, LLM_MODEL_2, LLM_MODEL_3, LLM_MODEL_4] if model]
if not LLM_MODEL_CATALOG:
    LLM_MODEL_CATALOG = [llm_model_info(LLM_MODEL)]
# Lista simple de pares valor/etiqueta para usar en formularios y selects.
LLM_MODEL_CHOICES = [(model['value'], model['label']) for model in LLM_MODEL_CATALOG]

# Tipo de campo por defecto para claves primarias.
# BigAutoField evita quedarse corto en tablas con muchos registros.
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Refuerzos de seguridad cuando DEBUG está desactivado.
# Solo se activan en producción para exigir HTTPS y endurecer cabeceras.
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    # Redirige automáticamente HTTP a HTTPS si se activa desde el entorno.
    SECURE_SSL_REDIRECT = env_first('DJANGO_SECURE_SSL_REDIRECT', default='False') == 'True'
