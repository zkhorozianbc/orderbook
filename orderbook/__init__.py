from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("orderbook")
except PackageNotFoundError:
    __version__ = "v0.4.1"

from orderbook.book import Book
from orderbook.level import PriceLevel
from orderbook.order import Order, OrderQueue, OrderStatus, Side
from orderbook.transaction import Transaction, TransactionSummary

easter_egg = "artificial lake"
__all__ = [
    "Book",
    "Order",
    "OrderQueue",
    "OrderStatus",
    "Side",
    "PriceLevel",
    "Transaction",
    "TransactionSummary",
    "easter_egg",
]
