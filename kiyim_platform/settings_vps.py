from .settings import *  # noqa: F403,F401
import os


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


DEBUG = _as_bool(os.getenv("DJANGO_DEBUG"), default=False)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", SECRET_KEY)  # noqa: F405
SERVE_MEDIA_WITH_DJANGO = _as_bool(os.getenv("DJANGO_SERVE_MEDIA"), default=True)
SERVE_STATIC_WITH_DJANGO = _as_bool(os.getenv("DJANGO_SERVE_STATIC"), default=True)
BEHIND_HTTPS_PROXY = _as_bool(os.getenv("DJANGO_BEHIND_HTTPS"), default=False)

_default_hosts = "127.0.0.1,localhost"
ALLOWED_HOSTS = [  # noqa: F405
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", _default_hosts).split(",")
    if host.strip()
]

_csrf_origins = os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "")
if _csrf_origins.strip():
    CSRF_TRUSTED_ORIGINS = [
        origin.strip()
        for origin in _csrf_origins.split(",")
        if origin.strip()
    ]

STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405
if not (BASE_DIR / "static").exists():  # noqa: F405
    STATICFILES_DIRS = []  # noqa: F405

MEDIA_ROOT = BASE_DIR / "media"  # noqa: F405
MEDIA_URL = "/media/"

if not DEBUG and BEHIND_HTTPS_PROXY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
