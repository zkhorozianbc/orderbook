from dataclasses import dataclass, field
from decimal import Decimal
from orderbook.order import OrderQueue, Side
from typing import TypeAlias
Price: TypeAlias = Decimal


@dataclass
class PriceLevel:
    side: Side
    price: Price
    orders: OrderQueue = field(default_factory=OrderQueue)

    def __lt__(self, other: "PriceLevel") -> bool:
        """BIDS should be max heap, asks min heap"""
        return self.side.price_comparator(self.price, other.price)
