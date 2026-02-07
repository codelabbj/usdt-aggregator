from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseP2PPlatform(ABC):
    """Interface pour toute plateforme P2P (Binance, Paxful, OKX, etc.)."""

    code: str = ""
    name: str = ""

    @abstractmethod
    def fetch_offers(
        self,
        asset: str,
        fiat: str,
        trade_type: str,
        country: Optional[str] = None,
        page: int = 1,
        rows: int = 20,
    ) -> List[Dict[str, Any]]:
        """Récupère les offres (BUY ou SELL) pour asset/fiat."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Vérifie si la plateforme répond (pour fallback)."""
        pass
