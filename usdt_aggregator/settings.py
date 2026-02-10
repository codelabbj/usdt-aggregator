import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# Charger les variables du fichier .env (à la racine du projet) dans os.environ
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-change-in-production")

DEBUG = os.environ.get("DEBUG", "1") == "1"

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "corsheaders",
    "core",
    "platforms",
    "offers",
    "rates",
    "api",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "api.middleware.api_key_usage_middleware",
]

ROOT_URLCONF = "usdt_aggregator.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "usdt_aggregator.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/admin/login/"

# REST Framework (API key ou JWT)
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "api.auth.APIKeyAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "api.auth.CheckAPIKeyQuota",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Pas de URLPathVersioning : le préfixe /api/v1/ est fixe, pas un paramètre de version DRF.
    # Garder DEFAULT_VERSIONING_CLASS vide évite "No operations defined in spec!" dans Swagger.
}

# OpenAPI / Swagger
SPECTACULAR_SETTINGS = {
    "TITLE": "USDT Aggregator API",
    "DESCRIPTION": "Offres P2P, taux croisés, paramètres dynamiques",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Cache Redis (fallback LocMem si REDIS_URL vide)
_redis_url = os.environ.get("REDIS_URL", "").strip()
if _redis_url:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": _redis_url,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "KEY_PREFIX": "usdt_agg",
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "KEY_PREFIX": "usdt_agg",
            "TIMEOUT": 300,
        }
    }

# Plateforme P2P par défaut
DEFAULT_P2P_PLATFORM = os.environ.get("DEFAULT_P2P_PLATFORM", "binance")

# Fuseau pour affichage
TIMEZONE_DISPLAY = os.environ.get("TIMEZONE_DISPLAY", "Africa/Abidjan")

# Mode sandbox API (réponses mock pour tests)
SANDBOX_API = os.environ.get("SANDBOX_API", "0") == "1"

# Refresh = seule source de vérité : les APIs lisent les offres depuis OffersSnapshot (pas d'appel plateforme).
USE_REFRESH_AS_SOURCE = os.environ.get("USE_REFRESH_AS_SOURCE", "1") == "1"

# Logging : console en INFO pour voir les logs du refresh best rates
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "core": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "offers": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "platforms": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
