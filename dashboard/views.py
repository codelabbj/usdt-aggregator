from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from django.utils import timezone
from decimal import Decimal
from core.models import LiquidityConfig, RateAdjustment, PlatformConfig, BestRatesRefreshConfig, APIKey, APIKeyUsage, BillingConfig
from platforms.registry import init_platforms, get_all_platforms, get_default_platform


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


@staff_member_required
def liquidity_config(request):
    configs = LiquidityConfig.objects.all().order_by("trade_type")
    return render(request, "dashboard/liquidity.html", {"configs": configs})


@require_http_methods(["GET", "POST"])
@staff_member_required
def liquidity_edit(request, trade_type):
    try:
        config = LiquidityConfig.objects.get(trade_type=trade_type)
    except LiquidityConfig.DoesNotExist:
        config = LiquidityConfig(trade_type=trade_type)
    if request.method == "POST":
        try:
            config.min_amount = request.POST.get("min_amount") or 0
            max_val = request.POST.get("max_amount")
            config.max_amount = max_val if max_val else None
            config.active = request.POST.get("active") == "on"
            config.save()
            messages.success(request, "Config liquidité enregistrée.")
            return redirect("dashboard:liquidity_config")
        except Exception as e:
            messages.error(request, str(e))
    return render(request, "dashboard/liquidity_edit.html", {"config": config})


@staff_member_required
def rate_adjustments(request):
    adjustments = RateAdjustment.objects.all().order_by("scope", "currency", "country")
    return render(request, "dashboard/rate_adjustments.html", {"adjustments": adjustments})


@require_http_methods(["GET", "POST"])
@staff_member_required
def rate_adjustment_edit(request, pk=None):
    if pk:
        adj = RateAdjustment.objects.get(pk=pk)
    else:
        adj = RateAdjustment()
    if request.method == "POST":
        try:
            adj.scope = request.POST.get("scope", adj.scope)
            adj.currency = request.POST.get("currency", "")
            adj.country = request.POST.get("country", "")
            adj.trade_type = request.POST.get("trade_type", "")
            adj.mode = request.POST.get("mode", adj.mode)
            adj.value = request.POST.get("value") or 0
            adj.active = request.POST.get("active") == "on"
            adj.save()
            messages.success(request, "Ajustement enregistré.")
            return redirect("dashboard:rate_adjustments")
        except Exception as e:
            messages.error(request, str(e))
    return render(request, "dashboard/rate_adjustment_edit.html", {"adjustment": adj})


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
