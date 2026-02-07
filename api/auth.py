from django.utils import timezone
from rest_framework import authentication
from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission
from core.models import APIKey, APIKeyUsage


class QuotaExceeded(APIException):
    """Quota mensuel d'appels API dépassé."""
    status_code = 429
    default_detail = "Quota mensuel dépassé."
    default_code = "quota_exceeded"


class CheckAPIKeyQuota(BasePermission):
    """Si authentifié par clé API avec monthly_quota, refuse (429) si quota déjà atteint."""

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        api_key = getattr(user, "api_key", None) if user else None
        if api_key is None or api_key.monthly_quota is None:
            return True
        period = timezone.now().strftime("%Y-%m")
        usage, _ = APIKeyUsage.objects.get_or_create(
            api_key=api_key, period=period, defaults={"call_count": 0}
        )
        if usage.call_count >= api_key.monthly_quota:
            raise QuotaExceeded(
                detail=f"Quota mensuel dépassé. Limite: {api_key.monthly_quota} appels/mois."
            )
        return True


class APIKeyAuthentication(authentication.BaseAuthentication):
    """Authentification par clé API (header X-API-Key ou Authorization: ApiKey <key>)."""
    keyword = "ApiKey"

    def authenticate(self, request):
        key = request.META.get("HTTP_X_API_KEY") or self._key_from_authorization(request)
        if not key:
            return None
        try:
            api_key = APIKey.objects.get(key=key, active=True)
        except APIKey.DoesNotExist:
            return None
        user = SimpleNamespace(is_authenticated=True, api_key=api_key)
        return (user, key)

    def _key_from_authorization(self, request):
        auth = request.META.get("HTTP_AUTHORIZATION")
        if auth and auth.startswith(f"{self.keyword} "):
            return auth[len(self.keyword) + 1 :].strip()
        return None
