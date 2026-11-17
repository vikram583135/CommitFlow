"""CI integration configuration; requires a disposable PostgreSQL instance."""
from .test_settings import *  # noqa: F403
import os

DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': os.getenv('TEST_POSTGRES_DB', 'commitflow_test'),
    'USER': os.getenv('TEST_POSTGRES_USER', 'commitflow_test'),
    'PASSWORD': os.getenv('TEST_POSTGRES_PASSWORD', 'commitflow_test'),
    'HOST': os.getenv('TEST_POSTGRES_HOST', 'localhost'),
    'PORT': os.getenv('TEST_POSTGRES_PORT', '5432'),
}}
