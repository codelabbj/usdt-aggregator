from django.apps import AppConfig


class PlatformsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "platforms"
    verbose_name = "Plateformes P2P"

    def ready(self):
        from .registry import init_platforms
        init_platforms()
