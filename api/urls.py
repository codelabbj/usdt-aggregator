from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

# APIs retenues : offres, cross rate, pays, devises (+ auth)
urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # API 1 : Offres (fiat, trade_type, country) — paginée
    path("offers/", views.offers_list),
    # API 1a : Même que offers/ mais réponse = uniquement les prix ajustés
    path("offers/prices/", views.offers_list_prices),
    # API 1b : Meilleures offres (top N)
    path("offers/best/", views.offers_best),
    # API 2 : Taux croisé + meilleures offres chaque côté
    path("rates/cross/", views.cross_rate),
    # API 3 : Liste des pays
    path("countries/", views.countries_list),
    # API 4 : Liste des devises
    path("currencies/", views.currencies_list),
    # API 5 : Résolution reference → annonceur (clés exemptes)
    path("advertiser/", views.advertiser_lookup),
    # --- Désactivés (hors scope) ---
    # path("offers/binance-raw/", views.offers_binance_raw),
    # path("rates/currencies/", views.rates_currencies_list),
    # path("platforms/", views.platforms_list),
    # path("xof-countries/", views.xof_countries_list),
    # path("best-rates/", views.best_rates_list),
]
