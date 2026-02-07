from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("offers/", views.offers_list),
    # path("offers/binance-raw/", views.offers_binance_raw),  # interne / tests uniquement
    path("rates/cross/", views.cross_rate),
    path("rates/usdt/", views.usdt_rate),
    path("rates/currencies/", views.rates_currencies_list),
    path("platforms/", views.platforms_list),
    path("xof-countries/", views.xof_countries_list),
    path("best-rates/", views.best_rates_list),
]
