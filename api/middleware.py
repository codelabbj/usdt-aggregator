"""
Comptage des appels API par clé (facturation).
Incrémente le compteur du mois pour chaque réponse 2xx authentifiée par clé API.
"""
from django.utils import timezone


def _get_api_key_from_request(request):
    """Retourne l'instance APIKey si la requête a été authentifiée par clé API."""
    if not hasattr(request, "user") or request.user is None:
        return None
    return getattr(request.user, "api_key", None)


def _get_or_create_usage(api_key, period):
    from core.models import APIKeyUsage
    obj, _ = APIKeyUsage.objects.get_or_create(
        api_key=api_key,
        period=period,
        defaults={"call_count": 0},
    )
    return obj


def api_key_usage_middleware(get_response):
    """En process_response : si authentifié par clé API et réponse 2xx → incrémenter le compteur du mois."""
    def middleware(request):
        if not request.path.startswith("/api/"):
            return get_response(request)

        response = get_response(request)

        api_key = _get_api_key_from_request(request)
        if api_key is None:
            return response

        period = timezone.now().strftime("%Y-%m")

        if 200 <= response.status_code < 300:
            try:
                usage = _get_or_create_usage(api_key, period)
                usage.call_count += 1
                usage.save(update_fields=["call_count"])
            except Exception:
                pass

        return response

    return middleware
