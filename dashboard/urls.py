from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_home, name="home"),
    path("offres/", views.offers_fetch, name="offers_fetch"),
    path("taux-croises/", views.cross_rates_list, name="cross_rates_list"),
    path("ajustement-taux-cross/", views.rate_cross, name="rate_cross"),
    path("ajustement-taux-cross/new/", views.rate_cross_edit, name="rate_cross_new"),
    path("ajustement-taux-cross/<int:pk>/edit/", views.rate_cross_edit, name="rate_cross_edit"),
    path("ajustement-taux-cross/<int:pk>/delete/", views.rate_cross_delete, name="rate_cross_delete"),
    path("api/", views.api_endpoints, name="api_endpoints"),
    path("liquidity/", views.liquidity_config, name="liquidity_config"),
    path("liquidity/<str:trade_type>/", views.liquidity_edit, name="liquidity_edit"),
    path("liquidity/<str:trade_type>/delete/", views.liquidity_delete, name="liquidity_delete"),
    path("rate-adjustments/", views.rate_adjustments, name="rate_adjustments"),
    path("rate-adjustments/new/", views.rate_adjustment_edit, name="rate_adjustment_new"),
    path("rate-adjustments/<int:pk>/", views.rate_adjustment_edit, name="rate_adjustment_edit"),
    path("rate-adjustments/<int:pk>/delete/", views.rate_adjustment_delete, name="rate_adjustment_delete"),
    path("platforms/", views.platform_config, name="platform_config"),
    path("platforms/set-default/", views.platform_set_default, name="platform_set_default"),
    path("refresh-config/", views.refresh_config, name="refresh_config"),
    path("facturation/", views.billing, name="billing"),
]
