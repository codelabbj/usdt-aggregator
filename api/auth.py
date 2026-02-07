from types import SimpleNamespace
from rest_framework import authentication
from core.models import APIKey


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
