from pydantic import BaseModel
from typing import List, Optional
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


class ItemPriceResponse(BaseModel):
    market_hash_name: str
    exterior: str
    stattrack: bool
    price_usd: float
    price_brl: Optional[float] = None
    currency: str
    source: str
    last_updated: str
    icon_url: Optional[str] = None


class InventoryAnalysisResponse(BaseModel):
    total_items: int
    total_value_usd: float
    items: List[dict]
    currency: str  # Sempre "USD"
    processed_at: str

