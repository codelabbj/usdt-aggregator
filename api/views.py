"""
API v1 : 4 endpoints retenus (+ auth).

1. GET /api/v1/offers/          — Offres (params: fiat, trade_type, country). Retourne prix, min_fiat, max_fiat, annonceur, moyens de paiement.
2. GET /api/v1/rates/cross/      — Taux croisé from → to via USDT + meilleures offres chaque côté (min/max, annonceur, paiement).
3. GET /api/v1/countries/       — Liste des pays (param fiat optionnel).
4. GET /api/v1/currencies/      — Liste des devises.
"""
from django.conf import settings
from rest_framework import status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiExample,
    OpenApiResponse,
    inline_serializer,
)

from core.models import BestRate, Currency, Country
from core.majoration import apply_majoration, apply_cross_adjustment
from offers.services import fetch_offers, fetch_offers_raw, get_offers_from_snapshot

SANDBOX_API = getattr(settings, "SANDBOX_API", False)


def _sandbox_offers(fiat, trade_type, country):
    if SANDBOX_API:
        p = 600 if fiat == "XOF" else 12.5
        return [{
            "platform": "sandbox", "price": p, "adjusted_price": p,
            "min_fiat": 3000, "max_fiat": 500000,
            "fiat": fiat, "trade_type": trade_type,
            "advertiser": {"nick_name": "Sandbox", "user_type": "user"},
            "payment_methods": [{"identifier": "MTNMobileMoney", "name": "MTN Mobile Money"}],
            "offer_id": "sandbox-1",
        }]
    return None


def _sandbox_cross_rate(from_c, to_c):
    if SANDBOX_API:
        return 48.0
    return None


# Schémas de réponse pour la doc Swagger
_OfferItemSerializer = inline_serializer(
    "OfferItem",
    fields={
        "platform": serializers.CharField(),
        "offer_id": serializers.CharField(required=False),
        "trade_type": serializers.CharField(),
        "price": serializers.FloatField(),
        "min_fiat": serializers.FloatField(),
        "max_fiat": serializers.FloatField(),
        "adjusted_price": serializers.FloatField(),
        "payment_methods": serializers.ListField(child=serializers.CharField(), required=False),
        "merchant": serializers.BooleanField(required=False),
    },
)
_OffersResponseSerializer = inline_serializer(
    "OffersResponse",
    fields={
        "count": serializers.IntegerField(),
        "page": serializers.IntegerField(),
        "page_size": serializers.IntegerField(),
        "offers": serializers.ListField(child=_OfferItemSerializer),
    },
)
_CrossRateResponseSerializer = inline_serializer(
    "CrossRateResponse",
    fields={
        "from_currency": serializers.CharField(),
        "to_currency": serializers.CharField(),
        "rate": serializers.FloatField(),
        "sandbox": serializers.BooleanField(),
    },
)
_ErrorResponseSerializer = inline_serializer(
    "ErrorResponse",
    fields={"error": serializers.CharField()},
)
_PlatformItemSerializer = inline_serializer(
    "PlatformItem",
    fields={"code": serializers.CharField(), "name": serializers.CharField()},
)
_PlatformsResponseSerializer = inline_serializer(
    "PlatformsResponse",
    fields={"platforms": serializers.ListField(child=_PlatformItemSerializer)},
)
_CountryItemSerializer = inline_serializer(
    "CountryItem",
    fields={"code": serializers.CharField(), "name": serializers.CharField()},
)
_CountryWithFiatItemSerializer = inline_serializer(
    "CountryWithFiatItem",
    fields={
        "code": serializers.CharField(),
        "name": serializers.CharField(),
        "fiat": serializers.CharField(),
    },
)
_XofCountriesResponseSerializer = inline_serializer(
    "XofCountriesResponse",
    fields={"countries": serializers.ListField(child=_CountryItemSerializer)},
)
_CurrenciesItemSerializer = inline_serializer(
    "CurrencyItem",
    fields={
        "code": serializers.CharField(),
        "name": serializers.CharField(),
    },
)
_BestRateItemSerializer = inline_serializer(
    "BestRateItem",
    fields={
        "fiat": serializers.CharField(),
        "trade_type": serializers.CharField(),
        "country": serializers.CharField(),
        "platform": serializers.CharField(),
        "rank": serializers.IntegerField(),
        "rate": serializers.FloatField(),
        "updated_at": serializers.DateTimeField(),
    },
)
_BestRatesResponseSerializer = inline_serializer(
    "BestRatesResponse",
    fields={"best_rates": serializers.ListField(child=_BestRateItemSerializer)},
)
_CurrenciesResponseSerializer = inline_serializer(
    "CurrenciesResponse",
    fields={"currencies": serializers.ListField(child=_CurrenciesItemSerializer)},
)


@extend_schema(
    parameters=[
        OpenApiParameter("fiat", str, description="Devise (XOF, GHS, XAF)"),
        OpenApiParameter("trade_type", str, description="BUY ou SELL"),
        OpenApiParameter("platform", str, required=False),
    ],
    responses={
        200: _OffersResponseSerializer,
    },
    examples=[
        OpenApiExample(
            "Offres paginées",
            value={
                "count": 1,
                "page": 1,
                "page_size": 20,
                "offers": [
                    {
                        "platform": "binance",
                        "offer_id": "12345",
                        "trade_type": "BUY",
                        "price": 567.13,
                        "min_fiat": 3000,
                        "max_fiat": 300000,
                        "adjusted_price": 567.13,
                        "payment_methods": ["MTNMobileMoney", "OrangeMoney"],
                        "merchant": False,
                    },
                ],
            },
            response_only=True,
        ),
    ],
)
def _format_offer_for_api(o: dict, country: str = None) -> dict:
    """Formate une offre pour l'API : price (brut), adjusted_price (après règle d'ajustement), min_fiat, max_fiat, annonceur, moyens de paiement."""
    return {
        "price": o.get("price"),
        "adjusted_price": o.get("adjusted_price") or o.get("price"),
        "country": country or o.get("country"),
        "fiat": o.get("fiat"),
        "trade_type": o.get("trade_type"),
        "min_fiat": o.get("min_fiat"),
        "max_fiat": o.get("max_fiat"),
        "advertiser": o.get("advertiser"),
        "payment_methods": o.get("payment_methods"),
        "offer_id": o.get("offer_id"),
        "platform": o.get("platform"),
    }


# ---------------------------------------------------------------------------
# API 1 : Offres (fiat, trade_type, country) — toutes les offres, format épuré
# ---------------------------------------------------------------------------
@extend_schema(
    parameters=[
        OpenApiParameter("fiat", str, description="Devise (XOF, GHS, etc.)"),
        OpenApiParameter("trade_type", str, description="BUY ou SELL"),
        OpenApiParameter("country", str, required=False, description="Code pays (ex. BJ, CI). Vide = tous les pays."),
        OpenApiParameter("page", int, required=False, description="Numéro de page (défaut 1)."),
        OpenApiParameter("page_size", int, required=False, description="Nombre d'offres par page (défaut 20, max 100)."),
    ],
    description="Récupère les offres selon fiat, trade_type et pays. Réponse paginée : count, page, page_size, offers.",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def offers_list(request):
    fiat = request.query_params.get("fiat", "XOF").strip().upper()
    trade_type = request.query_params.get("trade_type", "SELL").upper()
    if trade_type not in ("BUY", "SELL"):
        trade_type = "SELL"
    country = request.query_params.get("country") or None
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(100, max(1, int(request.query_params.get("page_size", 20))))
    except (TypeError, ValueError):
        page_size = 20
    if SANDBOX_API:
        data = _sandbox_offers(fiat, trade_type, country) or []
    else:
        data = fetch_offers(asset="USDT", fiat=fiat, trade_type=trade_type, country=country, platform_code=None)
    for o in data:
        o.setdefault("fiat", fiat)
    data = sorted(data, key=lambda x: (x.get("adjusted_price") or x.get("price") or 0), reverse=(trade_type == "SELL"))
    offers_clean = [_format_offer_for_api(o, country) for o in data]
    total = len(offers_clean)
    start = (page - 1) * page_size
    end = start + page_size
    offers_page = offers_clean[start:end]
    return Response({
        "count": total,
        "page": page,
        "page_size": page_size,
        "offers": offers_page,
    })


# ---------------------------------------------------------------------------
# API 1a : Offres — même logique que offers_list, réponse = uniquement les prix ajustés
# ---------------------------------------------------------------------------
@extend_schema(
    parameters=[
        OpenApiParameter("fiat", str, description="Devise (XOF, GHS, etc.)"),
        OpenApiParameter("trade_type", str, description="BUY ou SELL"),
        OpenApiParameter("country", str, required=False, description="Code pays (ex. BJ, CI). Vide = tous les pays."),
        OpenApiParameter("page", int, required=False, description="Numéro de page (défaut 1)."),
        OpenApiParameter("page_size", int, required=False, description="Nombre d'offres par page (défaut 20, max 100)."),
    ],
    description="Même paramètres et pagination que GET /offers/. Retourne uniquement la liste des prix ajustés (même ordre que les offres).",
    responses={
        200: inline_serializer(
            "OffersPricesResponse",
            fields={
                "count": serializers.IntegerField(),
                "page": serializers.IntegerField(),
                "page_size": serializers.IntegerField(),
                "adjusted_prices": serializers.ListField(child=serializers.FloatField()),
            },
        ),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def offers_list_prices(request):
    """Même logique que offers_list, mais la réponse ne contient que les prix ajustés (liste de floats)."""
    fiat = request.query_params.get("fiat", "XOF").strip().upper()
    trade_type = request.query_params.get("trade_type", "SELL").upper()
    if trade_type not in ("BUY", "SELL"):
        trade_type = "SELL"
    country = request.query_params.get("country") or None
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(100, max(1, int(request.query_params.get("page_size", 20))))
    except (TypeError, ValueError):
        page_size = 20
    if SANDBOX_API:
        data = _sandbox_offers(fiat, trade_type, country) or []
    else:
        data = fetch_offers(asset="USDT", fiat=fiat, trade_type=trade_type, country=country, platform_code=None)
    for o in data:
        o.setdefault("fiat", fiat)
    data = sorted(data, key=lambda x: (x.get("adjusted_price") or x.get("price") or 0), reverse=(trade_type == "SELL"))
    adjusted_prices = [float(o.get("adjusted_price") or o.get("price") or 0) for o in data]
    total = len(adjusted_prices)
    start = (page - 1) * page_size
    end = start + page_size
    prices_page = adjusted_prices[start:end]
    return Response({
        "count": total,
        "page": page,
        "page_size": page_size,
        "adjusted_prices": prices_page,
    })


# ---------------------------------------------------------------------------
# API 1b : Meilleures offres (top N, pas de pagination)
# ---------------------------------------------------------------------------
@extend_schema(
    parameters=[
        OpenApiParameter("fiat", str, description="Devise (XOF, GHS, etc.)"),
        OpenApiParameter("trade_type", str, description="BUY ou SELL"),
        OpenApiParameter("country", str, required=False, description="Code pays (ex. BJ, CI). Vide = tous les pays."),
        OpenApiParameter("limit", int, required=False, description="Nombre de meilleures offres à retourner (défaut 3, max 50)."),
    ],
    description="Retourne les N meilleures offres (tri par meilleur prix). Par défaut les 3 meilleures.",
    responses={200: _OffersResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def offers_best(request):
    fiat = request.query_params.get("fiat", "XOF").strip().upper()
    trade_type = request.query_params.get("trade_type", "SELL").upper()
    if trade_type not in ("BUY", "SELL"):
        trade_type = "SELL"
    country = request.query_params.get("country") or None
    try:
        limit = min(50, max(1, int(request.query_params.get("limit", 3))))
    except (TypeError, ValueError):
        limit = 3
    if SANDBOX_API:
        data = _sandbox_offers(fiat, trade_type, country) or []
    else:
        data = fetch_offers(asset="USDT", fiat=fiat, trade_type=trade_type, country=country, platform_code=None)
    for o in data:
        o.setdefault("fiat", fiat)
    data = sorted(data, key=lambda x: (x.get("adjusted_price") or x.get("price") or 0), reverse=(trade_type == "SELL"))
    offers_clean = [_format_offer_for_api(o, country) for o in data]
    offers_top = offers_clean[:limit]
    return Response({
        "count": len(offers_top),
        "page": 1,
        "page_size": len(offers_top),
        "offers": offers_top,
    })


# ---------------------------------------------------------------------------
# Endpoints commentés (hors scope des 4 APIs retenues)
# ---------------------------------------------------------------------------
# @extend_schema(...)
# @api_view(["GET"])
# @permission_classes([IsAuthenticated])
# def offers_binance_raw(request):
#     """Réponse brute Binance P2P (toutes pages). Désactivé."""
#     ...


# ---------------------------------------------------------------------------
# API 2 : Taux croisé (from → to via USDT) + meilleures offres chaque côté (min/max, annonceur, paiement)
# ---------------------------------------------------------------------------
@extend_schema(
    parameters=[
        OpenApiParameter("from_currency", str, description="Devise source (ex. XOF)"),
        OpenApiParameter("to_currency", str, description="Devise cible (ex. GHS)"),
        OpenApiParameter("country_from", str, required=False, description="Pays devise source. Vide = tous les pays."),
        OpenApiParameter("country_to", str, required=False, description="Pays devise cible. Vide = tous les pays."),
    ],
    description="Taux croisé 1 from_currency = X to_currency via USDT. Retourne le rate + la meilleure offre côté source (BUY) et côté cible (SELL) avec min/max, annonceur, moyens de paiement.",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cross_rate(request):
    from_c = request.query_params.get("from_currency", "XOF").strip().upper()
    to_c = request.query_params.get("to_currency", "GHS").strip().upper()
    country_from = request.query_params.get("country_from") or None
    country_to = request.query_params.get("country_to") or None
    if from_c == to_c:
        return Response({"from_currency": from_c, "to_currency": to_c, "rate": 1.0, "best_offer_from": None, "best_offer_to": None})
    if SANDBOX_API:
        rate = _sandbox_cross_rate(from_c, to_c)
        return Response({"from_currency": from_c, "to_currency": to_c, "rate": rate, "best_offer_from": None, "best_offer_to": None})
    # Cross : même source que les offres (snapshot si USE_REFRESH_AS_SOURCE, sinon live)
    use_refresh = getattr(settings, "USE_REFRESH_AS_SOURCE", False)
    if use_refresh:
        from platforms.registry import get_default_platform
        platform = get_default_platform()
        code = platform.code if platform else None
        if code:
            offers_from = get_offers_from_snapshot(code, from_c, "BUY", country_from)
            offers_to = get_offers_from_snapshot(code, to_c, "SELL", country_to)
        else:
            offers_from, offers_to = [], []
    else:
        offers_from = fetch_offers_raw(asset="USDT", fiat=from_c, trade_type="BUY", country=country_from, platform_code=None)
        offers_to = fetch_offers_raw(asset="USDT", fiat=to_c, trade_type="SELL", country=country_to, platform_code=None)
    for o in offers_from:
        o.setdefault("fiat", from_c)
    for o in offers_to:
        o.setdefault("fiat", to_c)
    offers_from = sorted(offers_from, key=lambda x: (x.get("price") or 0))  # BUY = prix le plus bas = meilleur
    offers_to = sorted(offers_to, key=lambda x: (x.get("price") or 0), reverse=True)  # SELL = prix le plus haut = meilleur
    best_from = offers_from[0] if offers_from else None
    best_to = offers_to[0] if offers_to else None

    # Erreur explicite : indiquer ce qui n'existe pas
    missing = []
    if not best_from:
        part = f"offres {from_c} BUY"
        if country_from:
            part += f" (pays: {country_from})"
        missing.append(part)
    if not best_to:
        part = f"offres {to_c} SELL"
        if country_to:
            part += f" (pays: {country_to})"
        missing.append(part)
    if missing:
        detail = "Taux croisé indisponible : " + "; ".join(missing) + "."
        return Response(
            {"error": "Taux non disponible", "detail": detail, "missing": missing},
            status=status.HTTP_404_NOT_FOUND,
        )

    price_buy_from = float(best_from.get("price") or 0)
    price_sell_to = float(best_to.get("price") or 0)
    if price_buy_from <= 0:
        detail = f"Taux croisé indisponible : prix invalide (<= 0) pour les offres {from_c} BUY."
        return Response(
            {"error": "Taux non disponible", "detail": detail, "missing": [f"prix valide pour {from_c} BUY"]},
            status=status.HTTP_404_NOT_FOUND,
        )
    rate = apply_cross_adjustment(price_buy_from, price_sell_to, from_c, to_c)
    return Response({
        "from_currency": from_c,
        "to_currency": to_c,
        "rate": round(rate, 8),
        "best_offer_from": _format_offer_for_api(best_from, country_from),
        "best_offer_to": _format_offer_for_api(best_to, country_to),
    })


# Liste des plateformes — désactivé (hors scope)
# def platforms_list(request): ...


# ---------------------------------------------------------------------------
# API 4 : Liste des devises (admin Core > Devises)
# ---------------------------------------------------------------------------
@extend_schema(
    parameters=[
        OpenApiParameter("trade_type", str, required=False, description="Filtrer par type (BUY/SELL) si best rate existant."),
    ],
    responses={200: _CurrenciesResponseSerializer},
    description="Liste des devises gérées (admin Core > Devises).",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def currencies_list(request):
    trade_type = request.query_params.get("trade_type")
    qs = Currency.objects.filter(active=True).order_by("order", "code")
    if trade_type:
        use_refresh = getattr(settings, "USE_REFRESH_AS_SOURCE", False)
        if use_refresh:
            from core.models import OffersSnapshot
            fiat_with_rate = set(
                OffersSnapshot.objects.filter(trade_type=trade_type.upper()).values_list("fiat", flat=True).distinct()
            )
        else:
            from core.models import BestRate
            fiat_with_rate = set(
                BestRate.objects.filter(trade_type=trade_type.upper()).values_list("fiat", flat=True).distinct()
            )
        qs = qs.filter(code__in=fiat_with_rate)
    currencies = [{"code": c.code, "name": c.name or ""} for c in qs]
    return Response({"currencies": currencies})


@extend_schema(
    parameters=[
        OpenApiParameter("fiat", str, required=False, description="Code devise (ex. XOF, GHS). Si absent : tous les pays avec leur devise."),
    ],
    description="Pays gérés (source : admin Core > Pays). Avec fiat : pays de cette devise. Sans fiat : tous les pays avec champ fiat.",
    responses={
        200: OpenApiResponse(
            description="Liste de pays (code, name et optionnellement fiat)",
        ),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def countries_list(request):
    """Pays gérés par devise. ?fiat=XOF → pays XOF. Sans param → tous les pays avec fiat."""
    fiat = request.query_params.get("fiat", "").strip().upper()
    if fiat:
        countries = Country.objects.filter(currency__code=fiat, active=True).order_by("order", "code")
        return Response({"countries": [{"code": c.code, "name": c.name} for c in countries]})
    countries = Country.objects.filter(active=True).select_related("currency").order_by("currency__order", "currency__code", "order", "code")
    return Response({
        "countries": [{"code": c.code, "name": c.name, "fiat": c.currency.code} for c in countries]
    })


# xof_countries_list — désactivé ; utiliser GET /countries/?fiat=XOF
# best_rates_list — désactivé (hors scope des 4 APIs)
