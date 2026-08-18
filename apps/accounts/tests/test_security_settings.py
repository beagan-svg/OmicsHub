"""Production session settings keep browser authentication on HTTPS."""

from __future__ import annotations

import importlib


def test_production_session_cookies_are_hardened(monkeypatch):
    """Require secure, HttpOnly, same-site cookies in production settings."""
    monkeypatch.setenv("ALLOWED_HOSTS", "example.org")
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "https://example.org")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "True")
    monkeypatch.setenv("CSRF_COOKIE_SECURE", "True")
    monkeypatch.setenv("CACHE_URL", "redis://redis-cache:6379/0")

    production_settings = importlib.import_module("omicshub.settings.prod")

    assert production_settings.SESSION_COOKIE_SECURE is True
    assert production_settings.SESSION_COOKIE_HTTPONLY is True
    assert production_settings.SESSION_COOKIE_SAMESITE == "Lax"
    assert production_settings.CSRF_COOKIE_SECURE is True
    assert production_settings.CSRF_COOKIE_SAMESITE == "Lax"
    assert production_settings.CACHES["default"]["LOCATION"] == "redis://redis-cache:6379/0"
