"""Hermetic test configuration; never uses a developer database or credentials."""
import os

os.environ['DEBUG'] = 'True'
os.environ['DJANGO_SECRET_KEY'] = 'commitflow-unit-tests-only-key-not-for-deployment'
os.environ['FIELD_ENCRYPTION_KEY'] = 'x4YKV6m_tTGevRvWh01yUHknXBFFJwPQd0xpCvagnVQ='
os.environ['USE_SQLITE'] = 'True'
from .settings import *  # noqa: E402,F403

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'
FRONTEND_URL = 'http://localhost:3000'
ALLOWED_HOSTS = ['testserver', 'localhost']
