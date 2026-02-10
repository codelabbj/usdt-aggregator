from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator

from django.utils import timezone
from decimal import Decimal
from core.models import (
    LiquidityConfig, RateAdjustment, CrossRateAdjustment,
    PlatformConfig, BestRatesRefreshConfig, APIKey, APIKeyUsage, BillingConfig,
    Currency, Country,
)
from platforms.registry import init_platforms, get_all_platforms, get_default_platform
from django.conf import settings
from offers.services import fetch_offers, fetch_offers_raw, get_offers_from_snapshot
from core.majoration import apply_cross_adjustment


def _parse_rate_adjustment_target(target: str):
    """Décompose target (SELL, XOF:SELL, XOF:BJ:SELL) en (trade_type, currency, country)."""
    target = (target or "").strip()
    if not target:
        return "SELL", "", ""
    parts = target.split(":")
    if len(parts) == 1:
        return (parts[0].upper(), "", "") if parts[0].upper() in ("BUY", "SELL") else ("SELL", "", "")
    if len(parts) == 2:
        return (parts[1].upper(), parts[0].upper(), "") if parts[1].upper() in ("BUY", "SELL") else ("SELL", parts[0].upper(), "")
    if len(parts) >= 3:
        return (parts[2].upper(), parts[0].upper(), parts[1].upper())
    return "SELL", "", ""


def _build_rate_adjustment_target(trade_type: str, currency: str, country: str) -> str:
    """Construit target à partir de type, devise, pays."""
    trade_type = (trade_type or "SELL").strip().upper()
    if trade_type not in ("BUY", "SELL"):
        trade_type = "SELL"
    currency = (currency or "").strip().upper()
    country = (country or "").strip()
    if not currency:
        return trade_type
    if not country:
        return f"{currency}:{trade_type}"
    return f"{currency}:{country}:{trade_type}"


@staff_member_required
def billing(request):
    """Page dashboard facturation : config globale, clés API, usage et montant estimé."""
    now = timezone.now()
    current_period = now.strftime("%Y-%m")
    billing_config = BillingConfig.objects.first()
    if not billing_config:
        billing_config = BillingConfig(price_per_call=Decimal("0"), currency="EUR")
    api_keys = list(APIKey.objects.all().order_by("-created_at"))
    usages = {
        (u.api_key_id, u.period): u.call_count
        for u in APIKeyUsage.objects.filter(api_key__in=api_keys)
    }
    price = billing_config.price_per_call
    rows = []
    for key in api_keys:
        current = usages.get((key.id, current_period), 0)
        other = [(p, c) for (kid, p), c in usages.items() if kid == key.id and p != current_period]
        other.sort(key=lambda x: x[0], reverse=True)
        if key.billing_exempt:
            estimated_amount = None
        else:
            estimated_amount = (Decimal(current) * price) if price else Decimal("0")
        rows.append({
            "key": key,
            "current_usage": current,
            "other_periods": other,
            "estimated_amount": estimated_amount,
        })
    return render(request, "dashboard/billing.html", {
        "billing_config": billing_config,
        "rows": rows,
        "current_period": current_period,
    })


@staff_member_required
def api_endpoints(request):
    """Page dashboard pour voir et tester les endpoints API."""
    return render(request, "dashboard/api_endpoints.html", {})


@staff_member_required
def dashboard_home(request):
    init_platforms()
    platforms = get_all_platforms()
    default = get_default_platform()
    return render(request, "dashboard/home.html", {
        "platforms": platforms,
        "default_platform": default.code if default else None,
    })


@require_http_methods(["GET", "POST"])
@staff_member_required
def liquidity_config(request):
    configs = LiquidityConfig.objects.all().order_by("trade_type")
    existing_types = set(c.trade_type for c in configs)
    trade_type_choices = [("BUY", "Achat (BUY)"), ("SELL", "Vente (SELL)")]
    can_add = len(configs) < 2

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add" and can_add:
            trade_type = request.POST.get("trade_type")
            if trade_type in ("BUY", "SELL") and trade_type not in existing_types:
                try:
                    min_val = request.POST.get("min_amount") or 0
                    max_val = request.POST.get("max_amount")
                    LiquidityConfig.objects.create(
                        trade_type=trade_type,
                        min_amount=Decimal(str(min_val)),
                        max_amount=Decimal(max_val) if max_val else None,
                        amount_in_fiat=request.POST.get("amount_in_fiat", "on") == "on",
                        require_inclusion=request.POST.get("require_inclusion") == "on",
                        active=request.POST.get("active") == "on",
                    )
                    messages.success(request, f"Config {trade_type} ajoutée.")
                except Exception as e:
                    messages.error(request, str(e))
            else:
                messages.error(request, "Type invalide ou déjà existant.")
            return redirect("dashboard:liquidity_config")
    available_to_add = [(code, label) for code, label in trade_type_choices if code not in existing_types]
    return render(request, "dashboard/liquidity.html", {
        "configs": configs,
        "can_add": can_add,
        "available_to_add": available_to_add,
    })


@require_http_methods(["GET", "POST"])
@staff_member_required
def liquidity_edit(request, trade_type):
    if trade_type not in ("BUY", "SELL"):
        messages.error(request, "Type invalide.")
        return redirect("dashboard:liquidity_config")
    try:
        config = LiquidityConfig.objects.get(trade_type=trade_type)
    except LiquidityConfig.DoesNotExist:
        config = LiquidityConfig(trade_type=trade_type)
    if request.method == "POST":
        try:
            config.min_amount = request.POST.get("min_amount") or 0
            max_val = request.POST.get("max_amount")
            config.max_amount = max_val if max_val else None
            config.require_inclusion = request.POST.get("require_inclusion") == "on"
            config.amount_in_fiat = request.POST.get("amount_in_fiat") == "on"
            config.active = request.POST.get("active") == "on"
            config.save()
            messages.success(request, "Config liquidité enregistrée.")
            return redirect("dashboard:liquidity_config")
        except Exception as e:
            messages.error(request, str(e))
    return render(request, "dashboard/liquidity_edit.html", {"config": config})


@require_http_methods(["POST"])
@staff_member_required
def liquidity_delete(request, trade_type):
    if trade_type not in ("BUY", "SELL"):
        messages.error(request, "Type invalide.")
        return redirect("dashboard:liquidity_config")
    try:
        config = LiquidityConfig.objects.get(trade_type=trade_type)
        config.delete()
        messages.success(request, f"Config {trade_type} supprimée.")
    except LiquidityConfig.DoesNotExist:
        messages.error(request, "Config introuvable.")
    return redirect("dashboard:liquidity_config")


@staff_member_required
def rate_adjustments(request):
    adjustments = RateAdjustment.objects.all().order_by("target", "id")
    return render(request, "dashboard/rate_adjustments.html", {"adjustments": adjustments})


@require_http_methods(["GET", "POST"])
@staff_member_required
def rate_adjustment_edit(request, pk=None):
    currencies = list(Currency.objects.filter(active=True).order_by("order", "code"))
    countries = list(Country.objects.filter(active=True).select_related("currency").order_by("currency__code", "order", "code"))
    if pk:
        adj = RateAdjustment.objects.get(pk=pk)
    else:
        adj = RateAdjustment()
        if request.method == "GET" and request.GET.get("target"):
            adj.target = request.GET.get("target", "").strip() or adj.target
    target_trade_type, target_currency, target_country = _parse_rate_adjustment_target(adj.target)
    if request.method == "POST":
        try:
            trade_type = request.POST.get("trade_type", target_trade_type)
            currency = request.POST.get("target_currency", "").strip()
            country = request.POST.get("target_country", "").strip()
            adj.target = _build_rate_adjustment_target(trade_type, currency, country)
            adj.mode = request.POST.get("mode", adj.mode)
            adj.value = request.POST.get("value") or 0
            adj.active = request.POST.get("active") == "on"
            adj.save()
            messages.success(request, "Ajustement enregistré.")
            return redirect("dashboard:rate_adjustments")
        except Exception as e:
            messages.error(request, str(e))
    return render(request, "dashboard/rate_adjustment_edit.html", {
        "adjustment": adj,
        "currencies": currencies,
        "countries": countries,
        "target_trade_type": target_trade_type,
        "target_currency": target_currency,
        "target_country": target_country,
    })


@require_http_methods(["POST"])
@staff_member_required
def rate_adjustment_delete(request, pk):
    """Supprimer un ajustement de taux (offres)."""
    try:
        adj = RateAdjustment.objects.get(pk=pk)
        adj.delete()
        messages.success(request, "Ajustement supprimé.")
    except RateAdjustment.DoesNotExist:
        messages.error(request, "Ajustement introuvable.")
    next_url = request.POST.get("next") or request.GET.get("next")
    return redirect(next_url if next_url else "dashboard:rate_adjustments")


@staff_member_required
def offers_fetch(request):
    """Page dashboard : formulaire (fiat, trade_type, pays, plateforme) → fetch des offres et affichage en tableau paginé."""
    init_platforms()
    platforms = get_all_platforms()
    default_platform = get_default_platform()
    currencies = list(Currency.objects.filter(active=True).order_by("order", "code"))
    countries = list(Country.objects.filter(active=True).select_related("currency").order_by("currency__code", "order", "code"))

    fiat = (request.GET.get("fiat") or "").strip().upper()
    trade_type = (request.GET.get("trade_type") or "").strip().upper()
    country = (request.GET.get("country") or "").strip() or None
    platform_code = (request.GET.get("platform") or "").strip() or None
    page_num = request.GET.get("page", "1")
    try:
        page_num = max(1, int(page_num))
    except ValueError:
        page_num = 1
    page_size = 25

    offers_list = []
    total_count = 0
    paginator = None
    page_obj = None

    if fiat and trade_type in ("BUY", "SELL"):
        offers_list = fetch_offers(
            asset="USDT",
            fiat=fiat,
            trade_type=trade_type,
            country=country,
            platform_code=platform_code if platform_code else None,
            use_cache=True,
        )
        total_count = len(offers_list)
        paginator = Paginator(offers_list, page_size)
        page_obj = paginator.get_page(page_num)

    return render(request, "dashboard/offers.html", {
        "currencies": currencies,
        "countries": countries,
        "platforms": platforms,
        "default_platform": default_platform.code if default_platform else None,
        "fiat": fiat,
        "trade_type": trade_type,
        "country": country or "",
        "platform_code": platform_code or "",
        "offers": page_obj.object_list if page_obj else [],
        "page_obj": page_obj,
        "total_count": total_count,
    })


def _compute_cross_rate_for_pair(from_c: str, to_c: str, country_from=None, country_to=None):
    """
    Calcule le taux croisé pour une paire (même logique que l'API).
    Retourne (rate, detail, missing) : rate float ou None ; si None, detail et missing décrivent ce qui manque.
    """
    if from_c == to_c:
        return (1.0, None, None)
    init_platforms()
    use_refresh = getattr(settings, "USE_REFRESH_AS_SOURCE", False)

    def get_offers_from(fiat, trade_type, country):
        if use_refresh:
            default_platform = get_default_platform()
            code = default_platform.code if default_platform else None
            if not code:
                return []
            offers = get_offers_from_snapshot(code, fiat, trade_type, country)
            # Fallback: si 0 offres pour ce pays, utiliser le snapshot "all" (country="")
            if not offers and country:
                offers = get_offers_from_snapshot(code, fiat, trade_type, None)
            return offers
        return fetch_offers_raw(asset="USDT", fiat=fiat, trade_type=trade_type, country=country, platform_code=None)

    offers_from = get_offers_from(from_c, "BUY", country_from)
    offers_to = get_offers_from(to_c, "SELL", country_to)

    offers_from = sorted(offers_from, key=lambda x: (x.get("price") or 0))
    offers_to = sorted(offers_to, key=lambda x: (x.get("price") or 0), reverse=True)
    best_from = offers_from[0] if offers_from else None
    best_to = offers_to[0] if offers_to else None

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
        return (None, detail, missing)

    price_buy_from = float(best_from.get("price") or 0)
    price_sell_to = float(best_to.get("price") or 0)
    if price_buy_from <= 0:
        detail = f"Taux croisé indisponible : prix invalide (<= 0) pour les offres {from_c} BUY."
        return (None, detail, [f"prix valide pour {from_c} BUY"])

    rate = apply_cross_adjustment(price_buy_from, price_sell_to, from_c, to_c)
    return (rate, None, None)


def _parse_cross_target(target: str):
    """Extrait (from_currency, to_currency) de target ex. cross:XOF:GHS -> (XOF, GHS)."""
    if not target or not target.startswith("cross"):
        return None, None
    parts = target.split(":")
    if len(parts) >= 3:
        return parts[1].upper(), parts[2].upper()
    if len(parts) == 2:
        return parts[1].upper(), None
    return None, None


@staff_member_required
def cross_rates_list(request):
    """Page dashboard : lister les taux croisés (formulaire from/to + pays → tableau des taux), comme la page Offres."""
    init_platforms()
    currencies = list(Currency.objects.filter(active=True).order_by("order", "code"))
    countries = list(Country.objects.filter(active=True).select_related("currency").order_by("currency__code", "order", "code"))

    from_c = (request.GET.get("from_currency") or "").strip().upper()
    to_c = (request.GET.get("to_currency") or "").strip().upper()
    country_from = (request.GET.get("country_from") or "").strip() or None
    country_to = (request.GET.get("country_to") or "").strip() or None

    rows = []
    if from_c:
        if to_c:
            if to_c == from_c:
                rows = [{"from_currency": from_c, "to_currency": to_c, "country_from": country_from or "—", "country_to": country_to or "—", "rate": 1.0, "detail": None, "missing": None}]
            else:
                rate, detail, missing = _compute_cross_rate_for_pair(from_c, to_c, country_from, country_to)
                rows = [{
                    "from_currency": from_c,
                    "to_currency": to_c,
                    "country_from": country_from or "—",
                    "country_to": country_to or "—",
                    "rate": round(rate, 8) if rate is not None else None,
                    "detail": detail,
                    "missing": missing,
                }]
        else:
            for c in currencies:
                if c.code == from_c:
                    continue
                rate, detail, missing = _compute_cross_rate_for_pair(from_c, c.code, country_from, country_to)
                rows.append({
                    "from_currency": from_c,
                    "to_currency": c.code,
                    "country_from": country_from or "—",
                    "country_to": country_to or "—",
                    "rate": round(rate, 8) if rate is not None else None,
                    "detail": detail,
                    "missing": missing,
                })

    return render(request, "dashboard/cross_rates_list.html", {
        "currencies": currencies,
        "countries": countries,
        "from_currency": from_c,
        "to_currency": to_c,
        "country_from": country_from or "",
        "country_to": country_to or "",
        "rows": rows,
    })


@staff_member_required
def rate_cross(request):
    """Page dashboard : liste des ajustements taux croisé + taux calculé pour chaque paire. Modifier / Supprimer / Ajouter."""
    adjustments = list(CrossRateAdjustment.objects.all().order_by("target"))
    rows = []
    for adj in adjustments:
        from_c, to_c = _parse_cross_target(adj.target)
        example_rate, _detail, _missing = None, None, None
        if from_c and to_c:
            example_rate, _detail, _missing = _compute_cross_rate_for_pair(from_c, to_c)
        rows.append({
            "adjustment": adj,
            "from_currency": from_c or "—",
            "to_currency": to_c or "—",
            "example_rate": round(example_rate, 8) if example_rate is not None else None,
        })

    return render(request, "dashboard/rate_cross.html", {"rows": rows})


@require_http_methods(["GET", "POST"])
@staff_member_required
def rate_cross_edit(request, pk=None):
    """Créer ou modifier un ajustement taux croisé."""
    if pk:
        adj = CrossRateAdjustment.objects.get(pk=pk)
    else:
        adj = CrossRateAdjustment(target="cross", mode=CrossRateAdjustment.MODE_PERCENT, value_buy=Decimal("0"), value_sell=Decimal("0"))
    if request.method == "POST":
        try:
            adj.target = (request.POST.get("target") or "cross").strip()
            adj.mode = request.POST.get("mode", adj.mode)
            adj.value_buy = Decimal(request.POST.get("value_buy") or "0")
            adj.value_sell = Decimal(request.POST.get("value_sell") or "0")
            adj.active = request.POST.get("active") == "on"
            adj.save()
            messages.success(request, "Ajustement croisé enregistré.")
            return redirect("dashboard:rate_cross")
        except Exception as e:
            messages.error(request, str(e))
    return render(request, "dashboard/rate_cross_edit.html", {"adjustment": adj})


@require_http_methods(["POST"])
@staff_member_required
def rate_cross_delete(request, pk):
    """Supprimer un ajustement taux croisé."""
    try:
        adj = CrossRateAdjustment.objects.get(pk=pk)
        adj.delete()
        messages.success(request, "Ajustement croisé supprimé.")
    except CrossRateAdjustment.DoesNotExist:
        messages.error(request, "Ajustement introuvable.")
    return redirect("dashboard:rate_cross")


@staff_member_required
def platform_config(request):
    platforms = list(PlatformConfig.objects.all())
    init_platforms()
    available = get_all_platforms()
    return render(request, "dashboard/platforms.html", {
        "platforms_db": platforms,
        "available": available,
        "default_platform": get_default_platform().code if get_default_platform() else None,
    })


@require_http_methods(["GET", "POST"])
@staff_member_required
def refresh_config(request):
    """Config du rafraîchissement des best rates (intervalle, actif)."""
    config = BestRatesRefreshConfig.objects.first()
    if not config:
        config = BestRatesRefreshConfig.objects.create(interval_minutes=5, is_active=True)
    if request.method == "POST":
        try:
            config.interval_minutes = int(request.POST.get("interval_minutes", config.interval_minutes))
            config.is_active = request.POST.get("is_active") == "on"
            config.save()
            messages.success(request, "Config refresh enregistrée.")
            return redirect("dashboard:refresh_config")
        except (ValueError, TypeError) as e:
            messages.error(request, "Valeur invalide.")
    return render(request, "dashboard/refresh_config.html", {"config": config})


@require_http_methods(["POST"])
@staff_member_required
def platform_set_default(request):
    """Définit la plateforme par défaut (config dashboard)."""
    code = request.POST.get("platform_code", "").strip()
    if not code:
        messages.error(request, "Code plateforme requis.")
        return redirect("dashboard:platform_config")
    init_platforms()
    available = get_all_platforms()
    if code not in available:
        messages.error(request, f"Plateforme « {code } » inconnue.")
        return redirect("dashboard:platform_config")
    PlatformConfig.objects.filter(is_default=True).update(is_default=False)
    obj, _ = PlatformConfig.objects.get_or_create(code=code, defaults={"name": available[code].name})
    obj.is_default = True
    obj.active = True
    obj.save()
    messages.success(request, f"Plateforme par défaut : {obj.name}.")
    return redirect("dashboard:platform_config")
