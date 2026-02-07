# Conformité aux spécifications fonctionnelles

## 1. Récupération des offres (Buy / Sell)

| Exigence | Statut | Détail |
|----------|--------|--------|
| Offres achat et vente USDT | ✅ | `fetch_offers(asset="USDT", trade_type="BUY"\|"SELL")` |
| Devises XOF, GHS, XAF | ✅ | Paramètre `fiat` (XOF, GHS, XAF) |
| Segmentation XOF par pays | ✅ | Paramètre `country` (ex. BJ, CI, SN). Liste des pays : `GET /api/v1/xof-countries/` |

## 2. Filtrage des offres par liquidité

| Exigence | Statut | Détail |
|----------|--------|--------|
| Quantité min/max BUY et SELL | ✅ | Modèle `LiquidityConfig` (min_amount, max_amount par trade_type) |
| Définition par l’admin via le dashboard | ✅ | Pages **Dashboard → Liquidité** (config BUY et SELL) |
| Exclusion automatique des offres hors critères | ✅ | `filter_by_liquidity()` dans `offers/services.py` |

## 3. Ajustement des taux (markup / markdown)

| Exigence | Statut | Détail |
|----------|--------|--------|
| Mode pourcentage (%) | ✅ | `RateAdjustment.mode = "percent"` |
| Mode montant fixe | ✅ | `RateAdjustment.mode = "fixed"` |
| Global | ✅ | `scope = "global"` |
| Par devise | ✅ | `scope = "currency"` + `currency` (XOF, GHS, XAF) |
| Par pays (XOF) | ✅ | `scope = "country"` + `country` |
| Par type d’offre (achat/vente) | ✅ | `scope = "trade_type"` + `trade_type` |
| Configurable via le dashboard | ✅ | **Dashboard → Ajustements de taux** |

## 4. Calcul automatique des taux croisés (cross-rate)

| Exigence | Statut | Détail |
|----------|--------|--------|
| Moteur de calcul (ex. XOF/USDT, USDT/GHS → XOF/GHS) | ✅ | `rates/services.compute_cross_rate()` |
| Taux précis et normalisés | ✅ | Moyenne des offres filtrées + ajustements ; arrondi 8 décimales |
| Temps réel ou fréquence définie | ✅ | Cache Redis/LocMem (TTL configurable) ; actualisation à chaque requête si cache expiré |

## 5. API publique / interne

| Exigence | Statut | Détail |
|----------|--------|--------|
| Récupérer les offres filtrées | ✅ | `GET /api/v1/offers/?fiat=&trade_type=&country=&platform=` |
| Obtenir les taux calculés | ✅ | `GET /api/v1/rates/usdt/`, `GET /api/v1/rates/cross/` |
| Paramètres dynamiques (devise, pays, quantité, type) | ✅ | Query params sur tous les endpoints concernés ; quantité = config admin (min/max) |
| Sécurisée (API key / JWT) | ✅ | JWT (`POST /api/v1/auth/token/`) + API Key (header `X-API-Key` ou `Authorization: ApiKey <key>`) |
| Versionnée | ✅ | Préfixe `/api/v1/` |
| Documentée (Swagger / OpenAPI) | ✅ | `/api/docs/` (Swagger UI), `/api/schema/` (OpenAPI) |

## 6. Support multi-plateformes

| Exigence | Statut | Détail |
|----------|--------|--------|
| Binance par défaut | ✅ | Plateforme `binance` enregistrée par défaut |
| Architecture extensible (Paxful, OKX, Bybit, etc.) | ✅ | Interface `BaseP2PPlatform` + registry dans `platforms/` |
| Plateforme définie via paramètre API | ✅ | `?platform=binance` sur `/api/v1/offers/` |
| Plateforme définie via configuration dashboard | ✅ | **Dashboard → Plateformes** : bouton « Définir par défaut » |

## 7. Fonctionnalités complémentaires

| Exigence | Statut | Détail |
|----------|--------|--------|
| Cache des taux et offres (Redis) | ✅ | Redis si `REDIS_URL` ; sinon LocMem ; TTL configurable |
| Logs et monitoring des variations de taux | ✅ | `logger.info` à chaque taux calculé ; comparaison avec dernier taux |
| Alertes en cas de variation anormale | ✅ | `logger.warning` si variation > 10 % entre deux calculs (même paire) |
| Fallback si une plateforme ne répond pas | ✅ | `_fetch_offers_with_fallback()` : essaie une autre plateforme en cas d’échec |
| Historique des taux (reporting, audit) | ✅ | Modèle `RateHistory` ; enregistrement à chaque calcul (USDT et cross-rate) |
| Mode sandbox pour les tests API | ✅ | `SANDBOX_API=1` : réponses mock (offres, taux USDT, cross-rate) |
| Gestion des fuseaux horaires et devises locales | ✅ | `TIMEZONE_DISPLAY` dans settings ; champs datés en UTC (USE_TZ=True) |
