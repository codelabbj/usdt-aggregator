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

from core.constants import XOF_COUNTRIES
from core.models import BestRate
from core.majoration import apply_majoration
from offers.services import fetch_offers
from rates.services import get_usdt_rate, compute_cross_rate
from platforms.registry import get_all_platforms, init_platforms
from platforms.binance import fetch_binance_p2p_raw

SANDBOX_API = getattr(settings, "SANDBOX_API", False)


def _sandbox_offers(fiat, trade_type, country):
    if SANDBOX_API:
        return [
            {"platform": "sandbox", "price": 600 if fiat == "XOF" else 12.5, "min_amount": 10, "max_amount": 5000, "adjusted_price": 610},
        ]
    return None


def _sandbox_usdt_rate(fiat, trade_type):
    if SANDBOX_API:
        return 600.0 if fiat == "XOF" else 12.45 if fiat == "GHS" else 600.0
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
        "min_amount": serializers.FloatField(),
        "max_amount": serializers.FloatField(),
        "available_amount": serializers.FloatField(required=False),
        "adjusted_price": serializers.FloatField(),
        "payment_methods": serializers.ListField(child=serializers.CharField(), required=False),
        "merchant": serializers.BooleanField(required=False),
    },
)
_OffersResponseSerializer = inline_serializer(
    "OffersResponse",
    fields={
        "count": serializers.IntegerField(),
        "offers": serializers.ListField(child=_OfferItemSerializer),
        "sandbox": serializers.BooleanField(),
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
_UsdtRateResponseSerializer = inline_serializer(
    "UsdtRateResponse",
    fields={
        "fiat": serializers.CharField(),
        "trade_type": serializers.CharField(),
        "country": serializers.CharField(allow_null=True, required=False),
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
_XofCountriesResponseSerializer = inline_serializer(
    "XofCountriesResponse",
    fields={"countries": serializers.ListField(child=_CountryItemSerializer)},
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
    fields={"currencies": serializers.ListField(child=serializers.CharField())},
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
            "10 meilleures offres (épurées)",
            value={
                "count": 1,
                "offers": [
                    {
                        "platform": "binance",
                        "offer_id": "12345",
                        "trade_type": "BUY",
                        "price": 567.13,
                        "min_amount": 3000,
                        "max_amount": 300000,
                        "available_amount": 300000,
                        "adjusted_price": 567.13,
                        "payment_methods": ["MTNMobileMoney", "OrangeMoney"],
                        "merchant": False,
                    },
                ],
                "sandbox": False,
            },
            response_only=True,
        ),
    ],
)
def _clean_offer(o):
    """Épure une offre pour la réponse API : pas de raw, payment_methods en noms simples."""
    pm = o.get("payment_methods") or []
    if isinstance(pm, list) and pm and isinstance(pm[0], dict):
        payment_names = [
            str(m.get("payType") or m.get("identifier") or m.get("tradeMethodName") or "")
            for m in pm
        ]
    else:
        payment_names = [str(p) for p in pm] if pm else []
    return {
        "platform": o.get("platform"),
        "offer_id": o.get("offer_id"),
        "trade_type": o.get("trade_type"),
        "price": o.get("price"),
        "min_amount": o.get("min_amount"),
        "max_amount": o.get("max_amount"),
        "available_amount": o.get("available_amount"),
        "adjusted_price": o.get("adjusted_price"),
        "payment_methods": payment_names,
        "merchant": o.get("merchant", False),
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def offers_list(request):
    fiat = request.query_params.get("fiat", "XOF")
    trade_type = request.query_params.get("trade_type", "SELL").upper()
    if trade_type not in ("BUY", "SELL"):
        trade_type = "SELL"
    platform = request.query_params.get("platform") or None
    if SANDBOX_API:
        data = _sandbox_offers(fiat, trade_type, None) or []
    else:
        data = fetch_offers(asset="USDT", fiat=fiat, trade_type=trade_type, country=None, platform_code=platform)
    # Meilleures offres : BUY = prix le plus bas d'abord, SELL = prix le plus haut d'abord
    data = sorted(data, key=lambda x: (x.get("adjusted_price") or x.get("price") or 0), reverse=(trade_type == "SELL"))
    data = data[:10]
    offers_clean = [_clean_offer(o) for o in data]
    return Response({"count": len(offers_clean), "offers": offers_clean, "sandbox": SANDBOX_API})


@extend_schema(
    summary="Offres Binance P2P (réponse brute)",
    description="Appel direct à l’API Binance P2P. Retourne exactement la réponse JSON de Binance (code, data avec adv, advertisers, etc.).",
    parameters=[
        OpenApiParameter("fiat", str, default="XOF", description="Devise (XOF, GHS, etc.)"),
        OpenApiParameter("trade_type", str, default="SELL", description="BUY ou SELL"),
        OpenApiParameter("country", str, required=False, description="Code pays (ex. BJ, CI)"),
        OpenApiParameter("page", int, default=1, description="Numéro de page"),
        OpenApiParameter("rows", int, default=20, description="Nombre d’offres par page"),
    ],
    responses={200: OpenApiResponse(description="Réponse brute Binance (code, data, total, ...)")},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def offers_binance_raw(request):
    """Retourne les offres telles qu’elles viennent de l’API Binance P2P (sans normalisation)."""
    fiat = request.query_params.get("fiat", "XOF")
    trade_type = request.query_params.get("trade_type", "SELL").upper()
    if trade_type not in ("BUY", "SELL"):
        trade_type = "SELL"
    country = request.query_params.get("country") or None
    try:
        page = int(request.query_params.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        rows = int(request.query_params.get("rows", 20))
    except (TypeError, ValueError):
        rows = 20
    try:
        data = fetch_binance_p2p_raw(
            asset="USDT",
            fiat=fiat,
            trade_type=trade_type,
            country=country,
            page=page,
            rows=rows,
        )
    except Exception as e:
        return Response(
            {"error": "Binance P2P indisponible", "detail": str(e)},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    return Response(data)


@extend_schema(
    parameters=[
        OpenApiParameter("from_currency", str, description="Devise source (ex. XOF)"),
        OpenApiParameter("to_currency", str, description="Devise cible (ex. GHS)"),
        OpenApiParameter("country_from", str, required=False, description="Pays devise source (ex. BJ, CI). Vide = tous les pays."),
        OpenApiParameter("country_to", str, required=False, description="Pays devise cible. Vide = tous les pays."),
    ],
    responses={
        200: _CrossRateResponseSerializer,
        404: OpenApiResponse(response=_ErrorResponseSerializer, description="Taux non disponible"),
    },
    description="Taux croisé from → to via USDT. Parcours réel : meilleur BUY pour la source, meilleur SELL pour la cible. rate = 1 from_currency = X to_currency. Sans pays = tous les pays.",
    examples=[
        OpenApiExample(
            "Taux croisé XOF → GHS",
            value={
                "from_currency": "XOF",
                "to_currency": "GHS",
                "rate": 0.02193,
                "sandbox": False,
            },
            response_only=True,
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cross_rate(request):
    from_c = request.query_params.get("from_currency", "XOF")
    to_c = request.query_params.get("to_currency", "GHS")
    country_from = request.query_params.get("country_from") or None
    country_to = request.query_params.get("country_to") or None
    if SANDBOX_API:
        rate = _sandbox_cross_rate(from_c, to_c)
    else:
        rate = compute_cross_rate(from_c, to_c, country_from=country_from, country_to=country_to)
    if rate is None:
        return Response({"error": "Taux non disponible"}, status=status.HTTP_404_NOT_FOUND)
    rate = apply_majoration(rate, from_c, "", country_from or "")
    return Response({"from_currency": from_c, "to_currency": to_c, "rate": rate, "sandbox": SANDBOX_API})


@extend_schema(
    parameters=[
        OpenApiParameter("fiat", str, description="XOF, GHS, XAF"),
        OpenApiParameter("trade_type", str, required=False),
        OpenApiParameter("country", str, required=False, description="Code pays (ex. BJ, CI). Vide = tous les pays."),
    ],
    responses={
        200: _UsdtRateResponseSerializer,
        404: OpenApiResponse(response=_ErrorResponseSerializer, description="Taux non disponible"),
    },
    examples=[
        OpenApiExample(
            "Taux USDT/XOF",
            value={
                "fiat": "XOF",
                "trade_type": "SELL",
                "country": None,
                "rate": 600.5,
                "sandbox": False,
            },
            response_only=True,
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def usdt_rate(request):
    fiat = request.query_params.get("fiat", "XOF")
    trade_type = request.query_params.get("trade_type", "SELL").upper()
    country = request.query_params.get("country") or None
    if SANDBOX_API:
        rate = _sandbox_usdt_rate(fiat, trade_type)
    else:
        rate = get_usdt_rate(fiat, trade_type, country=country)
    if rate is None:
        return Response({"error": "Taux non disponible"}, status=status.HTTP_404_NOT_FOUND)
    rate = apply_majoration(rate, fiat, trade_type, country or "")
    return Response({"fiat": fiat, "trade_type": trade_type, "country": country, "rate": rate, "sandbox": SANDBOX_API})


@extend_schema(
    responses={200: _PlatformsResponseSerializer},
    examples=[
        OpenApiExample(
            "Liste des plateformes",
            value={"platforms": [{"code": "binance", "name": "Binance P2P"}]},
            response_only=True,
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def platforms_list(request):
    init_platforms()
    pl = get_all_platforms()
    return Response({"platforms": [{"code": k, "name": v.name} for k, v in pl.items()]})


@extend_schema(
    parameters=[
        OpenApiParameter("trade_type", str, required=False, description="BUY ou SELL : ne retourner que les devises ayant un taux pour ce type"),
    ],
    responses={200: _CurrenciesResponseSerializer},
    description="Liste des devises pour lesquelles un taux USDT est disponible (source : best rates). Optionnellement filtré par trade_type.",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def rates_currencies_list(request):
    trade_type = request.query_params.get("trade_type")
    qs = BestRate.objects.values_list("fiat", flat=True).distinct()
    if trade_type:
        qs = BestRate.objects.filter(trade_type=trade_type.upper()).values_list("fiat", flat=True).distinct()
    currencies = sorted(set(qs))
    return Response({"currencies": currencies})


@extend_schema(
    description="Pays zone XOF pour segmentation des offres (paramètre country).",
    responses={200: _XofCountriesResponseSerializer},
    examples=[
        OpenApiExample(
            "Pays XOF",
            value={
                "countries": [
                    {"code": "BJ", "name": "Bénin"},
                    {"code": "CI", "name": "Côte d'Ivoire"},
                    {"code": "SN", "name": "Sénégal"},
                ]
            },
            response_only=True,
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def xof_countries_list(request):
    return Response({"countries": [{"code": c[0], "name": c[1]} for c in XOF_COUNTRIES]})


@extend_schema(
    parameters=[
        OpenApiParameter("fiat", str, required=False, description="Filtrer par devise (XOF, GHS, XAF)"),
        OpenApiParameter("trade_type", str, required=False, description="BUY ou SELL"),
        OpenApiParameter("country", str, required=False, description="Code pays (ex. BJ, CI). Vide = tous les pays (meilleurs taux agrégés)."),
    ],
    responses={200: _BestRatesResponseSerializer},
    description="Les 3 meilleurs taux USDT/fiat. Avec country = taux pour ce pays ; sans country = tous les pays. Alimenté par refresh_best_rates.",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def best_rates_list(request):
    qs = BestRate.objects.all().order_by("fiat", "trade_type", "country", "platform")
    fiat = request.query_params.get("fiat")
    if fiat:
        qs = qs.filter(fiat=fiat)
    trade_type = request.query_params.get("trade_type")
    if trade_type:
        qs = qs.filter(trade_type=trade_type.upper())
    country = request.query_params.get("country")
    if country is not None and country != "":
        qs = qs.filter(country=country)
    # Grouper par (fiat, trade_type) : avec country on a une seule valeur; sans country on agrège tous les pays et on prend le top 3
    from itertools import groupby
    data = []
    for (f, tt), group in groupby(qs, key=lambda r: (r.fiat, r.trade_type)):
        rows = list(group)
        rows.sort(key=lambda r: float(r.rate), reverse=(tt == "SELL"))
        for rank, r in enumerate(rows[:3], start=1):
            rate = apply_majoration(float(r.rate), r.fiat, r.trade_type, r.country or "")
            data.append({
                "fiat": r.fiat,
                "trade_type": r.trade_type,
                "country": r.country or None,
                "platform": r.platform,
                "rank": rank,
                "rate": rate,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            })
    return Response({"best_rates": data})
