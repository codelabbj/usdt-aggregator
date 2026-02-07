import requests
from typing import List, Dict, Any, Optional
from .base import BaseP2PPlatform

BINANCE_P2P_SEARCH_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"


def fetch_binance_p2p_raw(
    asset: str = "USDT",
    fiat: str = "XOF",
    trade_type: str = "SELL",
    country: Optional[str] = None,
    page: int = 1,
    rows: int = 20,
) -> Dict[str, Any]:
    """Appel direct à l'API Binance P2P ; retourne la réponse JSON brute telle quelle."""
    payload = {
        "asset": asset,
        "fiat": fiat,
        "merchantCheck": False,
        "page": page,
        "payTypes": [],
        "publisherType": None,
        "rows": rows,
        "tradeType": trade_type,
    }
    if country:
        payload["country"] = country
    r = requests.post(BINANCE_P2P_SEARCH_URL, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


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
    ) -> List[Dict[str, Any]]:
        payload = {
            "asset": asset,
            "fiat": fiat,
            "merchantCheck": False,
            "page": page,
            "payTypes": [],
            "publisherType": None,
            "rows": rows,
            "tradeType": trade_type,
        }
        if country:
            payload["country"] = country
        try:
            r = requests.post(BINANCE_P2P_SEARCH_URL, json=payload, timeout=15)
            r.raise_for_status()
            data = r.json()
            if data.get("code") != "000000":
                return []
            d = data.get("data") or {}
            if isinstance(d, list):
                adv_list = [item.get("adv") for item in d if isinstance(item, dict) and item.get("adv")]
                advertisers = {}
            else:
                adv_list = d.get("adv") or []
                advertisers = d.get("advertisers") or {}
            return self._normalize_offers(adv_list, advertisers)
        except Exception:
            return []

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
