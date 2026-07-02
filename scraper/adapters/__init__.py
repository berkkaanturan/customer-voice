"""Platform adapters for incremental scraping."""

from adapters.play_store import PlayStoreAdapter
from adapters.app_store import AppStoreAdapter
from adapters.sikayetvar import SikayetvarAdapter
from adapters.eksisozluk import EksiSozlukAdapter

__all__ = [
    "PlayStoreAdapter",
    "AppStoreAdapter",
    "SikayetvarAdapter",
    "EksiSozlukAdapter",
]
