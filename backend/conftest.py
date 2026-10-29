"""Pytest configuration: set environment before Django settings load."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("POSTGRES_DB", "testdb")
os.environ.setdefault("POSTGRES_USER", "testuser")
os.environ.setdefault("POSTGRES_PASSWORD", "testpass")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
os.environ.setdefault("DJANGO_DEBUG", "1")
os.environ.setdefault("BOT_TOKEN", "123456789:test:token")
os.environ.setdefault("INTERNAL_API_SECRET", "test-internal-secret")
