import logging
import requests
from typing import List, Dict, Any, Optional
from .base import BaseP2PPlatform

logger = logging.getLogger(__name__)

BINANCE_P2P_SEARCH_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"


def _binance_search_payload(
    asset: str,
    fiat: str,
    trade_type: str,
    page: int,
    rows: int,
    country: Optional[str] = None,
    pay_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Payload identique au frontend p2p.binance.com pour que les filtres (ex. countries) soient appliqués."""
    return {
        "asset": asset,
        "fiat": fiat,
        "page": page,
        "rows": rows,
        "tradeType": trade_type,
        "countries": [country] if country else [],
        "proMerchantAds": False,
        "shieldMerchantAds": False,
        "filterType": "all",
        "periods": [],
        "additionalKycVerifyFilter": 0,
        "publisherType": None,
        "payTypes": pay_types if pay_types is not None else [],
        "classifies": ["mass", "profession", "fiat_trade"],
        "tradedWith": False,
        "followed": False,
    }


def fetch_binance_p2p_raw(
    asset: str = "USDT",
    fiat: str = "XOF",
    trade_type: str = "SELL",
    country: Optional[str] = None,
    page: int = 1,
    rows: int = 20,
) -> Dict[str, Any]:
    """Appel direct à l'API Binance P2P ; retourne la réponse JSON brute (une page)."""
    payload = _binance_search_payload(asset, fiat, trade_type, page, rows, country=country)
    r = requests.post(BINANCE_P2P_SEARCH_URL, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_binance_p2p_raw_all_pages(
    asset: str = "USDT",
    fiat: str = "XOF",
    trade_type: str = "SELL",
    country: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Récupère toutes les pages Binance P2P, agrège les données et trie par meilleur prix.
    Retourne le même format que l'API (code, data, total, success), data = liste triée.
    Meilleur prix : SELL = prix croissant (moins cher d'abord), BUY = prix décroissant (plus cher d'abord).
    """
    all_items: List[Dict[str, Any]] = []
    page = 1
    page_size = 20
    total = 0
    code = "000000"
    while page <= 100:
        payload = _binance_search_payload(asset, fiat, trade_type, page, page_size, country=country)
        try:
            r = requests.post(BINANCE_P2P_SEARCH_URL, json=payload, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception:
            break
        code = data.get("code", "")
        if code != "000000":
            break
        total = data.get("total") or 0
        d = data.get("data") or []
        if isinstance(d, list):
            all_items.extend(d)
        else:
            break
        if len(d) < page_size or len(all_items) >= total:
            break
        page += 1
    # Trier par meilleur prix : SELL → croissant (bas prix = meilleur), BUY → décroissant (haut prix = meilleur)
    def price_key(item: Dict) -> float:
        adv = item.get("adv") or {}
        try:
            return float(adv.get("price") or 0)
        except (TypeError, ValueError):
            return 0.0

    all_items.sort(key=price_key, reverse=(trade_type == "BUY"))
    return {
        "code": code,
        "message": None,
        "messageDetail": None,
        "data": all_items,
        "total": len(all_items),
        "success": code == "000000",
    }


class BinanceP2PPlatform(BaseP2PPlatform):
    code = "binance"
    name = "Binance P2P"

    def fetch_offers(
        self,
        asset: str = "USDT",
        fiat: str = "XOF",
        trade_type: str = "SELL",
        country: Optional[str] = None,
        page: int = 1,
        rows: int = 20,
        fetch_all_pages: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        fetch_all_pages=True (défaut) : récupère toutes les pages (pagination) pour
        avoir l’ensemble des offres avant tri → vrais meilleurs taux.
        fetch_all_pages=False : un seul appel (page, rows) pour usage paginé côté API.
        """
        if not fetch_all_pages:
            return self._fetch_offers_page(asset, fiat, trade_type, country, page, rows)
        # Récupérer toutes les pages pour calculer les vrais meilleurs taux
        country_label = country or "all"
        logger.info("Binance: démarrage fetch fiat=%s country=%s trade_type=%s", fiat, country_label, trade_type)
        all_adv = []
        all_advertisers = {}
        p = 1
        page_size = min(rows, 20)
        max_pages = 100
        while p <= max_pages:
            adv_list, advertisers, total = self._fetch_offers_page_raw(
                asset, fiat, trade_type, country, p, page_size
            )
            logger.debug("Binance: page %s → %s annonces (total API=%s)", p, len(adv_list), total)
            all_adv.extend(adv_list)
            all_advertisers.update(advertisers)
            if not adv_list or len(adv_list) < page_size or len(all_adv) >= (total or 0):
                break
            p += 1
        result = self._normalize_offers(all_adv, all_advertisers)
        logger.info("Binance: fiat=%s country=%s trade_type=%s → %s offres (%s pages)", fiat, country_label, trade_type, len(result), p)
        return result

    def _fetch_offers_page(
        self,
        asset: str,
        fiat: str,
        trade_type: str,
        country: Optional[str],
        page: int,
        rows: int,
    ) -> List[Dict[str, Any]]:
        adv_list, advertisers, _ = self._fetch_offers_page_raw(
            asset, fiat, trade_type, country, page, rows
        )
        return self._normalize_offers(adv_list, advertisers)

    def _fetch_offers_page_raw(
        self,
        asset: str,
        fiat: str,
        trade_type: str,
        country: Optional[str],
        page: int,
        rows: int,
    ) -> tuple:
        """Une requête, retourne (liste adv, dict advertisers, total)."""
        payload = _binance_search_payload(asset, fiat, trade_type, page, rows, country=country)
        try:
            r = requests.post(BINANCE_P2P_SEARCH_URL, json=payload, timeout=15)
            r.raise_for_status()
            data = r.json()
            if data.get("code") != "000000":
                logger.warning("Binance API: code=%s page=%s fiat=%s", data.get("code"), page, fiat)
                return [], {}, 0
            d = data.get("data") or {}
            total = data.get("total") or 0
            if isinstance(d, list):
                adv_list = []
                advertisers = {}
                for item in d:
                    if not isinstance(item, dict):
                        continue
                    adv = item.get("adv")
                    ad = item.get("advertiser")
                    if adv:
                        if isinstance(ad, dict) and ad.get("userNo"):
                            adv = {**adv, "advertiserNo": ad["userNo"]}
                            advertisers[str(ad["userNo"])] = ad
                        adv_list.append(adv)
                return adv_list, advertisers, total
            adv_list = d.get("adv") or []
            advertisers = d.get("advertisers") or {}
            return adv_list, advertisers, total
        except Exception as e:
            logger.warning("Binance API: erreur requête page=%s fiat=%s — %s", page, fiat, e)
            return [], {}, 0

    def _normalize_offers(self, adv_list: List, advertisers: dict) -> List[Dict[str, Any]]:
        result = []
        for adv in adv_list or []:
            if not isinstance(adv, dict):
                continue
            adv_id = adv.get("adNo") or adv.get("advNo")
            user = advertisers.get(str(adv.get("advertiserNo") or adv.get("userId") or ""), {})
            if isinstance(user, list):
                user = user[0] if user else {}
            min_single = float(adv.get("minSingleTransAmount") or adv.get("minTradeAmount") or 0)
            max_single = float(adv.get("maxSingleTransAmount") or adv.get("maxTradeAmount") or 0)
            price = float(adv.get("price") or 0)
            result.append({
                "platform": self.code,
                "offer_id": str(adv_id or ""),
                "trade_type": adv.get("tradeType") or "SELL",
                "price": price,
                "min_amount": min_single,
                "max_amount": max_single,
                "available_amount": max_single,
                "payment_methods": adv.get("tradeMethods") or [],
                "merchant": bool(adv.get("merchant") or user.get("isMerchant")),
                "raw": adv,
            })
        return result

    def is_available(self) -> bool:
        try:
            r = requests.post(
                BINANCE_P2P_SEARCH_URL,
                json={"asset": "USDT", "fiat": "XOF", "tradeType": "SELL", "rows": 1, "page": 1},
                timeout=5,
            )
            return r.status_code == 200 and r.json().get("code") == "000000"
        except Exception:
            return False
