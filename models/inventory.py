from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class InventoryItem(BaseModel):
    name: str
    market_hash_name: str
    exterior: str
    stattrack: bool = False
    quantity: int = 1
    icon_url: Optional[str] = None
    assetid: Optional[str] = None
    rarity: Optional[str] = None
    category: Optional[str] = None


class ItemPriceRequest(BaseModel):
    market_hash_name: str
    exterior: str
    stattrack: bool = False


class InventoryAnalysisRequest(BaseModel):
    items: List[InventoryItem]


class PriceHistoryEntry(BaseModel):
    date: str
    price_usd: float
    price_cents: int
    volume: Optional[int] = None
    listings: Optional[int] = None


class PriceHistory(BaseModel):
    entries: List[PriceHistoryEntry]
    all_time_high: Optional[float] = None
    all_time_low: Optional[float] = None
    current_price: Optional[float] = None
    price_change_7d: Optional[float] = None
    price_change_30d: Optional[float] = None
    total_entries: int


class ItemPriceResponse(BaseModel):
    market_hash_name: str
    exterior: str
    stattrack: bool
    price_usd: Optional[float] = None  # None quando "Not possible"
    price_brl: Optional[float] = None
    currency: str
    source: str
    last_updated: str
    icon_url: Optional[str] = None
    not_possible: Optional[bool] = False  # True quando a skin não existe nessa condição
    message: Optional[str] = None  # Mensagem explicativa
    price_history: Optional[PriceHistory] = None  # Histórico de preços


class InventoryAnalysisResponse(BaseModel):
    total_items: int
    total_value_usd: float
    items: List[dict]
    currency: str  # Sempre "USD"
    processed_at: str

