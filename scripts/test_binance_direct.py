#!/usr/bin/env python3
"""
Appel direct à l'API Binance P2P (sans Django).
Compare les réponses avec et sans filtre pays pour GHS / NGN.

Usage (depuis la racine du projet) :
  python scripts/test_binance_direct.py
  python scripts/test_binance_direct.py --fiat NGN --country NG
"""
import argparse
import json
import sys

try:
    import requests
except ImportError:
    print("Erreur: installez requests (pip install requests)")
    sys.exit(1)

BINANCE_P2P_SEARCH_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"


def build_payload(fiat: str, trade_type: str, page: int = 1, rows: int = 20, country: str | None = None):
    return {
        "asset": "USDT",
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
        "payTypes": [],
        "classifies": ["mass", "profession", "fiat_trade"],
        "tradedWith": False,
        "followed": False,
    }


def call_binance(fiat: str, trade_type: str, country: str | None = None):
    payload = build_payload(fiat, trade_type, country=country)
    r = requests.post(BINANCE_P2P_SEARCH_URL, json=payload, timeout=15)
    r.raise_for_status()
    return payload, r.json()


def main():
    parser = argparse.ArgumentParser(description="Appel direct API Binance P2P")
    parser.add_argument("--fiat", default="GHS", help="Devise (ex: GHS, NGN, XOF)")
    parser.add_argument("--trade_type", default="SELL", choices=("BUY", "SELL"))
    parser.add_argument("--country", default=None, help="Code pays (ex: GH, NG). Vide = pas de filtre.")
    parser.add_argument("--compare", action="store_true", help="Comparer avec country vide puis avec pays (GHS→GH, NGN→NG)")
    args = parser.parse_args()

    fiat = args.fiat.upper()
    trade_type = args.trade_type.upper()
    country = (args.country or "").strip() or None

    if args.compare:
        # Test 1: sans pays
        print("=" * 60)
        print(f"1) Appel avec fiat={fiat}, trade_type={trade_type}, countries=[]")
        print("=" * 60)
        payload1, resp1 = call_binance(fiat, trade_type, country=None)
        print("Payload envoyé:", json.dumps({k: v for k, v in payload1.items() if k in ("asset", "fiat", "tradeType", "countries")}, indent=2))
        print("Réponse: code=%s, total=%s, success=%s" % (resp1.get("code"), resp1.get("total"), resp1.get("success")))
        data1 = resp1.get("data") or []
        print("Nombre d'annonces (data):", len(data1))
        if data1:
            adv = (data1[0].get("adv") or {})
            print("Première annonce - price:", adv.get("price"), "min:", adv.get("minSingleTransAmount"), "max:", adv.get("maxSingleTransAmount"))
        else:
            print("(aucune annonce)")
        print()

        # Test 2: avec pays (déduire du fiat si possible)
        country_map = {"GHS": "GH", "NGN": "NG", "XOF": None}
        country_to_try = country or country_map.get(fiat)
        if country_to_try:
            print("=" * 60)
            print(f"2) Appel avec fiat={fiat}, trade_type={trade_type}, countries=[\"{country_to_try}\"]")
            print("=" * 60)
            payload2, resp2 = call_binance(fiat, trade_type, country=country_to_try)
            print("Payload envoyé:", json.dumps({k: v for k, v in payload2.items() if k in ("asset", "fiat", "tradeType", "countries")}, indent=2))
            print("Réponse: code=%s, total=%s, success=%s" % (resp2.get("code"), resp2.get("total"), resp2.get("success")))
            data2 = resp2.get("data") or []
            print("Nombre d'annonces (data):", len(data2))
            if data2:
                adv = (data2[0].get("adv") or {})
                print("Première annonce - price:", adv.get("price"), "min:", adv.get("minSingleTransAmount"), "max:", adv.get("maxSingleTransAmount"))
            else:
                print("(aucune annonce)")
        else:
            print("2) Pas de pays par défaut pour", fiat, "- utilisez --country XX pour tester.")
        return

    # Appel unique
    print("=" * 60)
    print(f"Appel: fiat={fiat}, trade_type={trade_type}, country={country!r}")
    print("=" * 60)
    payload, resp = call_binance(fiat, trade_type, country=country)
    print("Payload (extrait):", json.dumps({k: v for k, v in payload.items() if k in ("asset", "fiat", "tradeType", "countries")}, indent=2))
    print()
    print("Réponse:")
    print("  code:", resp.get("code"))
    print("  total:", resp.get("total"))
    print("  success:", resp.get("success"))
    data = resp.get("data") or []
    print("  len(data):", len(data))
    if data:
        for i, item in enumerate(data[:3]):
            adv = item.get("adv") or {}
            print("  [%d] price=%s min=%s max=%s" % (i, adv.get("price"), adv.get("minSingleTransAmount"), adv.get("maxSingleTransAmount")))
    else:
        print("  (liste data vide)")


if __name__ == "__main__":
    main()
