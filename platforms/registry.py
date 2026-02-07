from typing import Dict, Type, Optional
from .base import BaseP2PPlatform
from .binance import BinanceP2PPlatform


_platforms: Dict[str, BaseP2PPlatform] = {}


def register_platform(platform: BaseP2PPlatform) -> None:
    _platforms[platform.code] = platform


def get_platform(code: str) -> Optional[BaseP2PPlatform]:
    return _platforms.get(code)


def get_all_platforms() -> Dict[str, BaseP2PPlatform]:
    return dict(_platforms)


def get_default_platform() -> Optional[BaseP2PPlatform]:
    """Plateforme par défaut : d'abord config dashboard (PlatformConfig.is_default), puis settings."""
    try:
        from core.models import PlatformConfig
        default = PlatformConfig.objects.filter(active=True, is_default=True).first()
        if default and _platforms.get(default.code):
            return _platforms[default.code]
    except Exception:
        pass
    from django.conf import settings
    code = getattr(settings, "DEFAULT_P2P_PLATFORM", "binance")
    return _platforms.get(code) or (_platforms.get("binance") if _platforms else None)


def init_platforms():
    if "binance" not in _platforms:
        register_platform(BinanceP2PPlatform())
