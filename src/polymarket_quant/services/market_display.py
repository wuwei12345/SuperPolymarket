from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from polymarket_quant.domain.market import CanonicalMarket
from polymarket_quant.domain.market_display import SimulatedMarketCard, SimulatedTradeDisplayRow
from polymarket_quant.services.operator_queries import OperatorFilters, OperatorQueryService
from polymarket_quant.storage.market_store import MarketStore


class LatestMarketDataReader(Protocol):
    def fetch_latest_state(self, limit: int = 100) -> list[dict[str, Any]]: ...


class MarketDisplayService:
    def __init__(
        self,
        *,
        market_store: MarketStore | None,
        query_service: OperatorQueryService,
        market_data_store: LatestMarketDataReader | None = None,
        latest_state_limit: int = 1000,
    ) -> None:
        self.market_store = market_store
        self.query_service = query_service
        self.market_data_store = market_data_store
        self.latest_state_limit = latest_state_limit

    def market_cards(
        self,
        filters: OperatorFilters | None = None,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        filters = filters or OperatorFilters()
        markets = self._load_markets(filters)
        latest_by_token = self._latest_state_by_token()
        positions_by_token = {
            str(row.get("token_id")): row
            for row in self.query_service.simulation_positions(filters)
            if row.get("token_id")
        }
        trades = self.query_service.simulation_trades(filters, limit=200)
        latest_trade_reason_by_token = {
            str(row.get("token_id")): row.get("reason_code")
            for row in trades
            if row.get("token_id") and row.get("reason_code")
        }

        cards = [
            self._build_card(
                market,
                latest_by_token=latest_by_token,
                positions_by_token=positions_by_token,
                latest_trade_reason_by_token=latest_trade_reason_by_token,
            )
            for market in markets
        ]
        cards.sort(
            key=lambda row: (
                row.position_size == 0,
                -(row.liquidity or Decimal("0")),
                row.end_date is None,
                row.end_date,
                row.question,
            )
        )
        return [card.model_dump() for card in cards[:limit]]

    def recent_trades(
        self,
        filters: OperatorFilters | None = None,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        filters = filters or OperatorFilters()
        markets = self._load_markets(filters)
        market_by_token = _market_by_token(markets)
        rows: list[SimulatedTradeDisplayRow] = []
        for trade in self.query_service.simulation_trades(filters, limit=limit):
            token_id = str(trade.get("token_id") or "")
            market = market_by_token.get(token_id)
            side = _side_for_token(market, token_id)
            price = _decimal(trade.get("price")) or Decimal("0")
            size = _decimal(trade.get("quantity")) or Decimal("0")
            rows.append(
                SimulatedTradeDisplayRow(
                    time=trade.get("time"),
                    strategy=trade.get("strategy"),
                    action=_display_action(trade.get("action"), trade.get("reason_code")),
                    market_question=(market.question if market else str(trade.get("market") or token_id)),
                    side=side,
                    price=price,
                    size=size,
                    notional=_decimal(trade.get("amount")) or price * size,
                    reason_code=trade.get("reason_code") or None,
                )
            )
        return [row.model_dump() for row in rows]

    def _build_card(
        self,
        market: CanonicalMarket,
        *,
        latest_by_token: dict[str, dict[str, Any]],
        positions_by_token: dict[str, dict[str, Any]],
        latest_trade_reason_by_token: dict[str, Any],
    ) -> SimulatedMarketCard:
        yes_state = latest_by_token.get(market.yes_token_id, {})
        no_state = latest_by_token.get(market.no_token_id, {})
        yes_price = _display_price(yes_state) or _raw_outcome_price(market, "Yes")
        no_price = _display_price(no_state) or _raw_outcome_price(market, "No")
        held_token_id, position = _market_position(market, positions_by_token)
        position_side = _side_for_token(market, held_token_id) if held_token_id else None
        current_price = (
            yes_price
            if held_token_id == market.yes_token_id
            else no_price
            if held_token_id == market.no_token_id
            else _decimal(position.get("current_price")) if position else None
        )
        position_size = abs(_decimal(position.get("quantity")) or Decimal("0")) if position else Decimal("0")
        avg_entry = _decimal(position.get("avg_price")) if position else None
        if avg_entry is None and position:
            avg_entry = _decimal(position.get("average_cost"))
        cost_basis = position_size * (avg_entry or Decimal("0"))
        current_value = position_size * (current_price or Decimal("0"))
        pnl = _decimal(position.get("pnl")) if position else Decimal("0")
        if pnl is None:
            pnl = current_value - cost_basis
        return SimulatedMarketCard(
            market_id=market.market_id,
            condition_id=market.condition_id,
            question=market.question,
            category=market.category,
            end_date=market.end_date,
            yes_token_id=market.yes_token_id,
            no_token_id=market.no_token_id,
            yes_price=yes_price,
            no_price=no_price,
            yes_probability_pct=_pct(yes_price),
            no_probability_pct=_pct(no_price),
            liquidity=_decimal(market.liquidity),
            volume=_raw_decimal(market, "volume", "volumeNum", "volumeClob"),
            volume_24h=_raw_decimal(market, "volume24hr", "volume24hrClob"),
            spread=_decimal(yes_state.get("spread"))
            or _decimal(no_state.get("spread"))
            or _raw_decimal(market, "spread"),
            last_trade_price=_decimal(yes_state.get("last_trade_price"))
            or _decimal(no_state.get("last_trade_price"))
            or _raw_decimal(market, "lastTradePrice"),
            position_side=position_side,
            position_size=position_size,
            avg_entry=avg_entry,
            current_price=current_price,
            current_value=current_value,
            cost_basis=cost_basis,
            pnl=pnl,
            pnl_pct=(pnl / cost_basis * Decimal("100")) if cost_basis else None,
            strategy_name=str(position.get("strategy")) if position else None,
            last_signal_reason=(
                latest_trade_reason_by_token.get(held_token_id) if held_token_id else None
            ),
        )

    def _load_markets(self, filters: OperatorFilters) -> list[CanonicalMarket]:
        markets: list[CanonicalMarket] = []
        if self.market_store is not None:
            try:
                markets = self.market_store.list_markets()
            except Exception:
                markets = []
        if filters.market:
            markets = [
                market
                for market in markets
                if filters.market in {market.market_id, market.condition_id, market.question}
            ]
        if filters.token:
            markets = [
                market
                for market in markets
                if filters.token in {market.yes_token_id, market.no_token_id}
            ]
        return markets

    def _latest_state_by_token(self) -> dict[str, dict[str, Any]]:
        if self.market_data_store is None:
            return {}
        try:
            rows = self.market_data_store.fetch_latest_state(limit=self.latest_state_limit)
        except Exception:
            return {}
        return {str(row.get("token_id")): row for row in rows if row.get("token_id")}


def _market_by_token(markets: list[CanonicalMarket]) -> dict[str, CanonicalMarket]:
    rows: dict[str, CanonicalMarket] = {}
    for market in markets:
        rows[market.yes_token_id] = market
        rows[market.no_token_id] = market
    return rows


def _market_position(
    market: CanonicalMarket,
    positions_by_token: dict[str, dict[str, Any]],
) -> tuple[str | None, dict[str, Any] | None]:
    for token_id in (market.yes_token_id, market.no_token_id):
        position = positions_by_token.get(token_id)
        if position and (_decimal(position.get("quantity")) or Decimal("0")) != 0:
            return token_id, position
    return None, None


def _display_price(row: dict[str, Any]) -> Decimal | None:
    return (
        _decimal(row.get("midpoint"))
        or _decimal(row.get("last_trade_price"))
        or _decimal(row.get("best_ask"))
        or _decimal(row.get("best_bid"))
    )


def _raw_outcome_price(market: CanonicalMarket, outcome: str) -> Decimal | None:
    raw = market.raw_gamma or {}
    outcomes = _json_list(raw.get("outcomes"))
    prices = _json_list(raw.get("outcomePrices"))
    if outcomes and prices:
        for index, raw_outcome in enumerate(outcomes):
            if str(raw_outcome).lower() == outcome.lower() and index < len(prices):
                return _decimal(prices[index])
    if outcome.lower() == "yes":
        return _raw_decimal(market, "bestBid", "lastTradePrice")
    if outcome.lower() == "no":
        yes_price = _raw_outcome_price(market, "Yes")
        return Decimal("1") - yes_price if yes_price is not None else None
    return None


def _raw_decimal(market: CanonicalMarket, *keys: str) -> Decimal | None:
    raw = market.raw_gamma or {}
    for key in keys:
        value = raw.get(key)
        parsed = _decimal(value)
        if parsed is not None:
            return parsed
    return None


def _side_for_token(market: CanonicalMarket | None, token_id: str | None) -> str | None:
    if market is None or not token_id:
        return None
    if token_id == market.yes_token_id:
        return "YES"
    if token_id == market.no_token_id:
        return "NO"
    return None


def _display_action(action: Any, reason_code: Any) -> str:
    reason = str(reason_code or "").lower()
    for candidate in ("enter", "add", "reduce", "exit", "close"):
        if candidate in reason:
            return "exit" if candidate == "close" else candidate
    value = str(action or "").lower()
    if value == "buy":
        return "enter"
    if value == "sell":
        return "reduce"
    return value or "fill"


def _pct(value: Decimal | None) -> Decimal | None:
    return value * Decimal("100") if value is not None else None


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []
