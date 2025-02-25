import heapq as pq
import logging
from collections import defaultdict
from decimal import Decimal
from typing import TypeAlias, overload
from uuid import UUID

from pyorderbook.level import PriceLevel
from pyorderbook.order import Order, Side
from pyorderbook.trade_blotter import Trade, TradeBlotter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Symbol: TypeAlias = str
Price: TypeAlias = Decimal
PriceLevelHeap: TypeAlias = list[PriceLevel]


class Book:
    """Main Order Book class. Orchestrates order handling and stores
    orders.
    """

    def __init__(self) -> None:
        """Creates required data structures for order matching"""
        self.levels: defaultdict[str, dict[Side, PriceLevelHeap]] = defaultdict(
            lambda: {Side.BID: [], Side.ASK: []}
        )
        self.level_map: defaultdict[str, dict[Side, dict[Price, PriceLevel]]] = defaultdict(
            lambda: {Side.BID: {}, Side.ASK: {}}
        )
        self.order_map: dict[UUID, Order] = {}

    @overload
    def match(self, orders: Order) -> TradeBlotter: ...

    @overload
    def match(self, orders: list[Order]) -> list[TradeBlotter]: ...

    def match(self, orders: Order | list[Order]) -> TradeBlotter | list[TradeBlotter]:
        """Match incoming order(s) against standing orders in the book.
        :param order: incoming order
        :returns: TradeBlotter object containing trade metadata on the trades
        which occured during the matching process
        """
        if isinstance(orders, list):
            return [self.match(order) for order in orders]
        elif isinstance(orders, Order):
            return self._match(orders)
        raise ValueError("Invalid input type", type(orders))

    def _match(self, incoming_order: Order) -> TradeBlotter:
        """Main Order procesing function which executes the price-time priority
        matching logic.
        :param incoming_order: incoming order
        :returns: TradeBlotter object containing trade metadata on the trades
        which occured during the matching process
        """
        logger.info("~~~ Processing order: %s", incoming_order)
        trades: list[Trade] = []
        price_comparator = incoming_order.side.price_comparator
        levels = self.levels[incoming_order.symbol][incoming_order.side.other]
        while incoming_order.quantity and levels:
            level = levels[0]
            if not price_comparator(incoming_order.price, level.price):
                break
            while incoming_order.quantity and level.orders:
                best_standing_order = level.orders.peek()
                trade: Trade = self.fill(incoming_order, best_standing_order)
                trades.append(trade)
                if not best_standing_order.quantity:
                    logger.debug(
                        "Filled standing Order Id: %s from book: %s",
                        best_standing_order.id,
                    )
                    level.orders.popleft()
                    self.order_map.pop(best_standing_order.id)

            if not level.orders:
                logger.info(
                    "Flushing Price Level for %s at %s price %s",
                    incoming_order.symbol,
                    str(level.side),
                    level.price,
                )
                self.level_map[incoming_order.symbol][level.side].pop(level.price)
                pq.heappop(self.levels[incoming_order.symbol][level.side])

        if incoming_order.quantity:
            self.enqueue_order(incoming_order)

        trade_blotter = TradeBlotter(incoming_order, trades)
        logger.info("%s", trade_blotter)
        return trade_blotter

    def cancel(self, order: Order) -> None:
        """Cancel Standing Order. Remove order from its price level and delete
        reference in order id map
        :param order_id: id field of Order object
        :returns: False if order doesn't exist or if it's already cancelled,
        True if cancelled successfully.
        """
        order_id = order.id
        logger.info("~~~ Processing Cancel Request for Order Id", order_id)
        try:
            self.order_map.pop(order.id)
        except KeyError:
            logger.error("Order %s doesnt exist", order_id)
            raise

        level = self.get_level(order.symbol, order.side, order.price)
        if level is None:
            raise ValueError(
                f"Price Level {order.symbol}:{order.side}:{order.price} doesn't exist!"
            )
        level.orders.pop(order_id)

    def fill(
        self,
        incoming_order: Order,
        standing_order: Order,
    ) -> Trade:
        """Execute order fill. Updates incoming and standing order objects, determines
        trade price based on side, and matched quantity, and
        returns Trade object containing trade metadata.
        :param standing_order: standing order
        :param incoming_order: incoming order
        :returns: Trade object containing metadata on the matched price/quantity and
        order id of the matched orders
        """
        matched_quantity: int = min(standing_order.quantity, incoming_order.quantity)
        standing_order.quantity -= matched_quantity
        incoming_order.quantity -= matched_quantity
        fill_price = incoming_order.side.calc_fill_price(incoming_order.price, standing_order.price)
        trade = Trade(incoming_order.id, standing_order.id, matched_quantity, fill_price)
        logger.info("Filled Order: %s", trade)
        return trade

    def get_level(self, symbol: str, side: Side, price: Decimal) -> PriceLevel | None:
        """Return price level queue for a symbol/side/price
        :param symbol: order symbol
        :param side: order side
        :param price: order price
        :returns: price level (OrderQueue)
        """
        return self.level_map[symbol][side].get(price, None)

    def enqueue_order(self, order: Order) -> None:
        """Add order to book.
        - enqueue order to price level
        - add reference to order in order_map
        :param order: order to add to book
        :returns: None
        """
        logger.info("Adding Order to book: %s", order)
        level = self.get_level(order.symbol, order.side, order.price)
        if level is None:
            # create price level
            level = PriceLevel(order.side, order.price)
            # add level object to self.levels heap
            pq.heappush(self.levels[order.symbol][order.side], level)
            # add level reference to level map
            self.level_map[order.symbol][order.side][order.price] = level
        level.orders.append_order(order)
        self.order_map[order.id] = order

    def get_order(self, order_id: UUID) -> Order | None:
        """Return order object from order id
        :param order_id: id field of Order object
        :returns: Order object
        """
        return self.order_map.get(order_id, None)
