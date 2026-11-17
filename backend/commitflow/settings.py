"""
Django settings for CommitFlow project.
"""

from pathlib import Path
import os
from django.core.exceptions import ImproperlyConfigured
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file from project root or backend dir
load_dotenv(BASE_DIR.parent / '.env')
load_dotenv(BASE_DIR / '.env')

DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY') or ('django-insecure-dev-key-commitflow' if DEBUG else '')
if not DEBUG and (len(SECRET_KEY) < 50 or 'insecure' in SECRET_KEY.lower()):
    raise ImproperlyConfigured('Set a unique DJANGO_SECRET_KEY of at least 50 characters for production.')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000').rstrip('/')

ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,web').split(',') if h.strip()]
CSRF_TRUSTED_ORIGINS = [FRONTEND_URL]
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = not DEBUG
SECURE_REDIRECT_EXEMPT = [r'^health/$', r'^api/health/$']
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party packages
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_celery_beat',

    # CommitFlow Local Apps
    'apps.authentication',
    'apps.github_integration',
    'apps.ai_engine',
    'apps.automations',
    'apps.executions',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'commitflow.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'commitflow.wsgi.application'
ASGI_APPLICATION = 'commitflow.asgi.application'

# Database
USE_SQLITE = os.getenv('USE_SQLITE', 'False').lower() in ('true', '1', 't')
postgres_host = os.getenv('POSTGRES_HOST')

if postgres_host and not USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB', 'commitflow'),
            'USER': os.getenv('POSTGRES_USER', 'commitflow_user'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'commitflow_password'),
            'HOST': postgres_host,
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_USER_MODEL = 'authentication.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.authentication.token_auth.ExpiringTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'apps.common.pagination.BoundedPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.UserRateThrottle', 'rest_framework.throttling.AnonRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'user': '1000/hour', 'anon': '100/hour', 'auth': '20/minute', 'run': '5/minute', 'email': '5/hour'},
}
API_TOKEN_TTL = int(os.getenv('API_TOKEN_TTL', '86400'))
MAX_DAILY_EXECUTIONS = int(os.getenv('MAX_DAILY_EXECUTIONS', '20'))
ENABLE_PYTHON_SANDBOX = os.getenv('ENABLE_PYTHON_SANDBOX', 'False').lower() == 'true'
PYTHON_SANDBOX_IMAGE = os.getenv('PYTHON_SANDBOX_IMAGE', 'python:3.12-slim')
DATA_UPLOAD_MAX_MEMORY_SIZE = 300_000
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'CommitFlow <noreply@localhost>')
PASSWORD_RESET_TIMEOUT = 3600
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'} if DEBUG else {
    'BACKEND': 'django.core.cache.backends.redis.RedisCache',
    'LOCATION': os.getenv('REDIS_URL', 'redis://redis:6379/1'),
}}

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    FRONTEND_URL,
]
if DEBUG:
    CORS_ALLOWED_ORIGINS = list(set(CORS_ALLOWED_ORIGINS + ['http://127.0.0.1:3000', 'http://localhost:3000']))
CORS_ALLOW_CREDENTIALS = True

# Celery Configuration
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Field Encryption Key (Fernet 32-byte urlsafe base64)
FIELD_ENCRYPTION_KEY = os.getenv('FIELD_ENCRYPTION_KEY') or (
    'x4YKV6m_tTGevRvWh01yUHknXBFFJwPQd0xpCvagnVQ=' if DEBUG else '')
try:
    Fernet(FIELD_ENCRYPTION_KEY.encode())
except (ValueError, TypeError) as exc:
    raise ImproperlyConfigured('FIELD_ENCRYPTION_KEY must be a generated Fernet key.') from exc
if not DEBUG and FIELD_ENCRYPTION_KEY == 'x4YKV6m_tTGevRvWh01yUHknXBFFJwPQd0xpCvagnVQ=':
    raise ImproperlyConfigured('Generate a unique production FIELD_ENCRYPTION_KEY.')

# GitHub App Settings
GITHUB_APP_ID = os.getenv('GITHUB_APP_ID', '')
GITHUB_APP_NAME = os.getenv('GITHUB_APP_NAME', 'commitflow-bot')
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID', '')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET', '')
GITHUB_WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET', '')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
CELERY_TASK_SOFT_TIME_LIMIT = 300
CELERY_TASK_TIME_LIMIT = 330
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
