from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from polymarket_quant.adapters.polymarket import ClobClient
from polymarket_quant.adapters.polymarket_ws import MarketWebSocketClient
from polymarket_quant.domain.market_data import (
    BestBidAsk,
    BookLevel,
    BookSnapshot,
    GapFillInterval,
    LastTrade,
    RawPayloadEnvelope,
    ReferenceToken,
)
from polymarket_quant.services.backfill import MarketDataBackfillService
from polymarket_quant.services.universe_selector import UniverseSelector
from polymarket_quant.storage.market_data_store import MarketDataStore
from polymarket_quant.storage.market_store import MarketStore


@dataclass(frozen=True)
class RealtimeCollectorEvent:
    timestamp: datetime
    step: str
    source: str
    status: str
    message: str
    token_id: str | None = None
    gap_fill: bool = False


@dataclass(frozen=True)
class RealtimeCollectorResult:
    message_count: int
    raw_event_count: int
    normalized_count: int
    events: list[RealtimeCollectorEvent] = field(default_factory=list)


@dataclass(frozen=True)
class SubscriptionPoolConfig:
    hot_size: int = 50
    warm_size: int = 100
    warm_rotation_seconds: int = 600
    cold_sample_seconds: int = 3600


@dataclass
class SubscriptionPools:
    hot: list[ReferenceToken]
    warm: list[ReferenceToken]
    cold: list[ReferenceToken]
    config: SubscriptionPoolConfig
    _last_cold_sample_at: datetime | None = None

    def next_subscription_batch(self, now: datetime) -> list[ReferenceToken]:
        batch = list(self.hot)
        if self.warm:
            slice_size = max(1, self.config.hot_size)
            rotation = int(now.timestamp() // self.config.warm_rotation_seconds)
            start = (rotation * slice_size) % len(self.warm)
            doubled = [*self.warm, *self.warm]
            batch.extend(doubled[start : start + min(slice_size, len(self.warm))])
        if self.cold and self._should_sample_cold(now):
            batch.extend(self.cold)
            self._last_cold_sample_at = now
        return _dedupe_tokens(batch)

    def _should_sample_cold(self, now: datetime) -> bool:
        if self._last_cold_sample_at is None:
            return True
        elapsed = (now - self._last_cold_sample_at).total_seconds()
        return elapsed >= self.config.cold_sample_seconds


def assign_subscription_pools(
    tokens: list[ReferenceToken],
    config: SubscriptionPoolConfig,
) -> SubscriptionPools:
    ordered = sorted(tokens, key=lambda token: token.universe_rank)
    hot = ordered[: config.hot_size]
    warm = ordered[config.hot_size : config.hot_size + config.warm_size]
    cold = ordered[config.hot_size + config.warm_size :]
    return SubscriptionPools(hot=hot, warm=warm, cold=cold, config=config)


class WebSocketClient(Protocol):
    async def subscribe(self, token_ids: list[str]): ...


class MarketRealtimeCollector:
    def __init__(
        self,
        ws_client: WebSocketClient,
        store: MarketDataStore,
        tokens: list[ReferenceToken],
        max_messages: int | None = None,
        connection_id: str | None = None,
        gap_fill_service: "GapFillService | None" = None,
    ) -> None:
        self.ws_client = ws_client
        self.store = store
        self.tokens = tokens
        self.token_by_id = {token.token_id: token for token in tokens}
        self.max_messages = max_messages
        self.connection_id = connection_id or f"conn-{int(utc_now().timestamp())}"
        self.gap_fill_service = gap_fill_service

    async def collect_once(self) -> RealtimeCollectorResult:
        events = [
            _event("Realtime collection started", "CLOB_WS", "running", "Subscribed")
        ]
        message_count = 0
        raw_event_count = 0
        normalized_count = 0
        gap_started_at = utc_now()
        token_ids = [token.token_id for token in self.tokens]
        try:
            async for message in self.ws_client.subscribe(token_ids):
                message_count += 1
                self.store.insert_raw_ws_event(self._raw_envelope(message))
                raw_event_count += 1
                normalized_count += self._normalize_message(message, events)
                if self.max_messages is not None and message_count >= self.max_messages:
                    break
        except Exception as error:
            events.append(
                _event(
                    "Realtime reconnect scheduled",
                    "CLOB_WS",
                    "retrying",
                    str(error),
                )
            )
            if self.gap_fill_service is not None:
                events.extend(
                    self.gap_fill_service.fill_gap(
                        token_ids,
                        gap_started_at=gap_started_at,
                        gap_ended_at=utc_now(),
                        connection_id=self.connection_id,
                    )
                )
        if message_count == 0:
            events.append(
                _event(
                    "Realtime collection ended without messages",
                    "CLOB_WS",
                    "warning",
                    "No WebSocket market events were received before the connection ended",
                )
            )
        return RealtimeCollectorResult(
            message_count=message_count,
            raw_event_count=raw_event_count,
            normalized_count=normalized_count,
            events=events,
        )

    def _raw_envelope(self, message: dict[str, Any]) -> RawPayloadEnvelope:
        token_id = _message_token_id(message)
        return RawPayloadEnvelope(
            source="CLOB_WS",
            endpoint="market",
            payload=message,
            token_id=token_id,
            condition_id=message.get("market"),
            source_ts=_parse_source_ts(message.get("timestamp")),
            received_at=utc_now(),
            connection_id=self.connection_id,
        )

    def _normalize_message(
        self,
        message: dict[str, Any],
        events: list[RealtimeCollectorEvent],
    ) -> int:
        event_type = message.get("event_type")
        if event_type == "book":
            return self._normalize_book(message)
        if event_type == "price_change":
            return self._normalize_price_change(message)
        if event_type == "best_bid_ask":
            return self._normalize_best_bid_ask(message)
        if event_type == "last_trade_price":
            return self._normalize_last_trade(message)
        if event_type == "tick_size_change":
            events.append(
                _event(
                    "Tick size change captured",
                    "CLOB_WS",
                    "success",
                    "Raw tick_size_change event persisted",
                    token_id=_message_token_id(message),
                )
            )
            return 0
        events.append(
            _event("Unknown event captured", "CLOB_WS", "warning", str(event_type))
        )
        return 0

    def _normalize_book(self, message: dict[str, Any]) -> int:
        token = self._token(message.get("asset_id"))
        if token is None:
            return 0
        bids = [_book_level("BUY", row) for row in message.get("bids", [])]
        asks = [_book_level("SELL", row) for row in message.get("asks", [])]
        bids = [level for level in bids if level is not None]
        asks = [level for level in asks if level is not None]
        snapshot = BookSnapshot(
            token_id=token.token_id,
            condition_id=token.condition_id or message.get("market"),
            market=message.get("market"),
            source_ts=_parse_source_ts(message.get("timestamp")),
            received_at=utc_now(),
            source="CLOB_WS",
            hash=message.get("hash"),
            bids=bids,
            asks=asks,
        )
        self.store.insert_book_snapshot(snapshot)
        bbo = _best_bid_ask_from_levels(token, bids, asks, snapshot.source_ts)
        if bbo is not None:
            self.store.upsert_best_bid_ask([bbo])
            return 2
        return 1

    def _normalize_price_change(self, message: dict[str, Any]) -> int:
        rows: list[BestBidAsk] = []
        source_ts = _parse_source_ts(message.get("timestamp"))
        for change in message.get("price_changes", []):
            token = self._token(change.get("asset_id"))
            if token is None:
                continue
            rows.append(
                _best_bid_ask_from_values(
                    token,
                    best_bid=change.get("best_bid"),
                    best_ask=change.get("best_ask"),
                    source_ts=source_ts,
                )
            )
        self.store.upsert_best_bid_ask(rows)
        return len(rows)

    def _normalize_best_bid_ask(self, message: dict[str, Any]) -> int:
        token = self._token(message.get("asset_id"))
        if token is None:
            return 0
        row = _best_bid_ask_from_values(
            token,
            best_bid=message.get("best_bid"),
            best_ask=message.get("best_ask"),
            spread=message.get("spread"),
            source_ts=_parse_source_ts(message.get("timestamp")),
            connection_id=self.connection_id,
        )
        self.store.upsert_best_bid_ask([row])
        return 1

    def _normalize_last_trade(self, message: dict[str, Any]) -> int:
        token = self._token(message.get("asset_id"))
        if token is None or message.get("price") in (None, ""):
            return 0
        self.store.upsert_last_trades(
            [
                LastTrade(
                    token_id=token.token_id,
                    condition_id=token.condition_id or message.get("market"),
                    price=Decimal(str(message["price"])),
                    side=message.get("side"),
                    size=_optional_decimal(message.get("size")),
                    source_ts=_parse_source_ts(message.get("timestamp")),
                    received_at=utc_now(),
                    source="CLOB_WS",
                    connection_id=self.connection_id,
                )
            ]
        )
        return 1

    def _token(self, token_id: Any) -> ReferenceToken | None:
        if token_id in (None, ""):
            return None
        return self.token_by_id.get(str(token_id))


class GapFillService:
    def __init__(
        self,
        clob_client: ClobClient,
        store: MarketDataStore,
        recent_history_minutes: int = 60,
        book_chunk_size: int = 100,
    ) -> None:
        self.clob_client = clob_client
        self.store = store
        self.recent_history_minutes = recent_history_minutes
        self.book_chunk_size = book_chunk_size

    def fill_gap(
        self,
        token_ids: list[str],
        gap_started_at: datetime,
        gap_ended_at: datetime,
        connection_id: str,
    ) -> list[RealtimeCollectorEvent]:
        self.store.record_gap_interval(
            GapFillInterval(
                token_ids=token_ids,
                gap_started_at=gap_started_at,
                gap_ended_at=gap_ended_at,
                connection_id=connection_id,
                created_at=utc_now(),
            )
        )
        selector = _StaticTokenSelector(
            [
                ReferenceToken(
                    token_id=token_id,
                    question="Gap fill token",
                    outcome="Yes",
                    universe_rank=index + 1,
                    selection_reason="gap_fill",
                )
                for index, token_id in enumerate(token_ids)
            ]
        )
        service = MarketDataBackfillService(
            selector,
            self.clob_client,
            self.store,
            book_chunk_size=self.book_chunk_size,
        )
        start_ts = int(
            (gap_ended_at - timedelta(minutes=self.recent_history_minutes)).timestamp()
        )
        end_ts = int(gap_ended_at.timestamp())
        service.backfill_top_tokens(
            start_ts=start_ts,
            end_ts=end_ts,
            gap_fill=True,
            upsert_reference=False,
        )
        return [
            _event(
                "Gap fill completed",
                "CLOB_REST",
                "success",
                f"Gap filled {len(token_ids)} tokens",
                gap_fill=True,
            )
        ]


class _StaticTokenSelector:
    def __init__(self, tokens: list[ReferenceToken]) -> None:
        self.tokens = tokens

    def select_top_tokens(self) -> list[ReferenceToken]:
        return self.tokens


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _event(
    step: str,
    source: str,
    status: str,
    message: str,
    token_id: str | None = None,
    gap_fill: bool = False,
) -> RealtimeCollectorEvent:
    return RealtimeCollectorEvent(
        timestamp=utc_now(),
        step=step,
        source=source,
        status=status,
        message=message,
        token_id=token_id,
        gap_fill=gap_fill,
    )


def _dedupe_tokens(tokens: list[ReferenceToken]) -> list[ReferenceToken]:
    seen: set[str] = set()
    deduped: list[ReferenceToken] = []
    for token in tokens:
        if token.token_id not in seen:
            seen.add(token.token_id)
            deduped.append(token)
    return deduped


def _message_token_id(message: dict[str, Any]) -> str | None:
    value = message.get("asset_id")
    if value not in (None, ""):
        return str(value)
    changes = message.get("price_changes")
    if isinstance(changes, list) and changes:
        first = changes[0]
        if isinstance(first, dict) and first.get("asset_id") not in (None, ""):
            return str(first["asset_id"])
    return None


def _book_level(side: str, row: dict[str, Any]) -> BookLevel | None:
    if "price" not in row or "size" not in row:
        return None
    return BookLevel(
        side=side,
        price=Decimal(str(row["price"])),
        size=Decimal(str(row["size"])),
    )


def _best_bid_ask_from_levels(
    token: ReferenceToken,
    bids: list[BookLevel],
    asks: list[BookLevel],
    source_ts: datetime | None,
) -> BestBidAsk | None:
    best_bid = max((bid.price for bid in bids), default=None)
    best_ask = min((ask.price for ask in asks), default=None)
    if best_bid is None and best_ask is None:
        return None
    return _best_bid_ask_from_decimals(token, best_bid, best_ask, source_ts)


def _best_bid_ask_from_values(
    token: ReferenceToken,
    best_bid: Any,
    best_ask: Any,
    source_ts: datetime | None,
    spread: Any = None,
    connection_id: str | None = None,
) -> BestBidAsk:
    bid = _optional_decimal(best_bid)
    ask = _optional_decimal(best_ask)
    row = _best_bid_ask_from_decimals(token, bid, ask, source_ts, connection_id)
    if spread not in (None, ""):
        row.spread = Decimal(str(spread))
    return row


def _best_bid_ask_from_decimals(
    token: ReferenceToken,
    best_bid: Decimal | None,
    best_ask: Decimal | None,
    source_ts: datetime | None,
    connection_id: str | None = None,
) -> BestBidAsk:
    spread = best_ask - best_bid if best_bid is not None and best_ask is not None else None
    midpoint = (
        (best_ask + best_bid) / Decimal("2")
        if best_bid is not None and best_ask is not None
        else None
    )
    return BestBidAsk(
        token_id=token.token_id,
        condition_id=token.condition_id,
        best_bid=best_bid,
        best_ask=best_ask,
        spread=spread,
        midpoint=midpoint,
        source_ts=source_ts,
        received_at=utc_now(),
        source="CLOB_WS",
        connection_id=connection_id,
    )


def _parse_source_ts(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    if timestamp > 10_000_000_000:
        timestamp = timestamp // 1000
    return datetime.fromtimestamp(timestamp, timezone.utc)


def _optional_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


async def _run_once() -> None:
    top_n = int(os.getenv("POLYMARKET_TOP_N", "50"))
    raw_max_messages = os.getenv("POLYMARKET_MAX_MESSAGES")
    max_messages = int(raw_max_messages) if raw_max_messages else None
    market_store = MarketStore(Path("data/markets.sqlite3"))
    selector = UniverseSelector(market_store, top_n=top_n)
    tokens = selector.select_top_tokens()
    store = MarketDataStore()
    gap_fill = GapFillService(ClobClient(), store)
    collector = MarketRealtimeCollector(
        MarketWebSocketClient(),
        store,
        tokens,
        max_messages=max_messages,
        gap_fill_service=gap_fill,
    )
    result = await collector.collect_once()
    print(f"Collected {result.message_count} messages")
    for event in result.events:
        print(f"{event.status}: {event.step} - {event.message}")
    if result.message_count == 0:
        raise RuntimeError(
            "Realtime collector received zero WebSocket messages; check websocket dependency, token IDs, and network connectivity"
        )


def main() -> None:
    asyncio.run(_run_once())


if __name__ == "__main__":
    main()
