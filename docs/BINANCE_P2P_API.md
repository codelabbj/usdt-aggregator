# API Binance P2P utilisée par le projet

Cette API **n’est pas documentée officiellement** par Binance. Elle est utilisée par la page [p2p.binance.com](https://p2p.binance.com). Le projet s’en sert pour récupérer les annonces P2P (offres d’achat/vente USDT vs fiat).

---

## Endpoint

| | |
|---|---|
| **URL** | `https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search` |
| **Méthode** | `POST` |
| **Content-Type** | `application/json` |
| **Authentification** | Aucune (appel public) |

---

## Corps de la requête (JSON)

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `asset` | string | oui | Crypto (ex. `USDT`) |
| `fiat` | string | oui | Devise fiat (ex. `XOF`, `GHS`, `XAF`) |
| `tradeType` | string | oui | `BUY` ou `SELL` (côté annonceur) |
| `page` | int | non | Numéro de page (défaut `1`) |
| `rows` | int | non | Nombre d’annonces par page (défaut `20`) |
| `payTypes` | array | non | Filtre moyens de paiement (ex. `["MTNMobileMoney"]`), vide = tous |
| `country` | string | non | Filtre pays (ex. pour XOF) |
| `merchantCheck` | bool | non | Filtrer marchands vérifiés (défaut `false`) |
| `publisherType` | null / string | non | Souvent `null` |

Exemple minimal :

```json
{
  "asset": "USDT",
  "fiat": "XOF",
  "tradeType": "BUY",
  "page": 1,
  "rows": 20,
  "payTypes": [],
  "merchantCheck": false,
  "publisherType": null
}
```

---

## Réponse (JSON)

Structure globale :

```json
{
  "code": "000000",
  "message": null,
  "messageDetail": null,
  "data": [ { "adv": { ... }, "advertiser": { ... } }, ... ],
  "total": 407,
  "success": true
}
```

- **code** : `"000000"` = succès.
- **data** : liste d’objets ; chaque objet contient au moins `adv` (l’annonce) et `advertiser` (l’annonceur).
- **total** : nombre total d’annonces (pour pagination).

### Objet `adv` (annonce)

Champs principaux utilisés ou utiles :

| Champ | Type | Description |
|-------|------|-------------|
| `advNo` | string | ID de l’annonce |
| `tradeType` | string | `BUY` ou `SELL` |
| `asset` | string | ex. `USDT` |
| `fiatUnit` | string | ex. `XOF` |
| `fiatSymbol` | string | ex. `FCFA` |
| `price` | string | Prix (fiat par unité de crypto) |
| `minSingleTransAmount` | string | Montant fiat min par transaction |
| `maxSingleTransAmount` | string | Montant fiat max par transaction |
| `surplusAmount` / `tradableQuantity` | string | Quantité crypto disponible |
| **`remarks`** | string / null | **Commentaire / description de l’annonce** |
| **`autoReplyMsg`** | string / null | **Message de réponse automatique** |
| `tradeMethods` | array | Moyens de paiement (ex. MoMo, MTN, Wave) |
| `payTimeLimit` | int | Délai de paiement (minutes) |
| `classify` | string | ex. `mass`, `profession` |

### Objet `advertiser` (annonceur)

| Champ | Type | Description |
|-------|------|-------------|
| `userNo` | string | ID utilisateur |
| `nickName` | string | Pseudo |
| `userType` | string | ex. `user`, `merchant` |
| `monthOrderCount` | int | Commandes ce mois |
| `monthFinishRate` | float | Taux d’exécution (0–1) |
| `positiveRate` | float | Avis positifs (0–1) |
| `userGrade` | int | Niveau utilisateur |
| `activeTimeInSecond` | int | Dernière activité (secondes) |

---

## Où c’est utilisé dans le projet

- **`platforms/binance.py`** : `BINANCE_P2P_SEARCH_URL`, `fetch_binance_p2p_raw()` (une page), `fetch_binance_p2p_raw_all_pages()` (toutes les pages, tri par meilleur prix), `BinanceP2PPlatform.fetch_offers()`.
- **`api/views.py`** : vue `offers_binance_raw` (GET `/api/v1/offers/binance-raw/`) appelle `fetch_binance_p2p_raw_all_pages()` : **toutes les pages** sont récupérées, agrégées et **triées par meilleur prix** (SELL = prix croissant, BUY = prix décroissant). Paramètres : `fiat`, `trade_type`, `country` (pas de `page` ni `rows`).

Les champs **`remarks`** et **`autoReplyMsg`** existent bien dans la réponse ; s’ils sont souvent `null`, c’est que les annonceurs ne les remplissent pas toujours. Quand ils sont renseignés, ils sont présents dans le JSON retourné par cette API.
