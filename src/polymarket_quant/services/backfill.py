from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Protocol

from polymarket_quant.adapters.polymarket import ClobClient
from polymarket_quant.domain.market_data import (
    BestBidAsk,
    BookLevel,
    BookSnapshot,
    LastTrade,
    PriceHistoryPoint,
    RawPayloadEnvelope,
    ReferenceToken,
)
from polymarket_quant.services.universe_selector import UniverseSelector
from polymarket_quant.storage.market_data_store import MarketDataStore
from polymarket_quant.storage.market_store import MarketStore


@dataclass(frozen=True)
class BackfillEvent:
    timestamp: datetime
    step: str
    source: str
    status: str
    message: str
    token_id: str | None = None
    gap_fill: bool = False


@dataclass(frozen=True)
class BackfillResult:
    selected_count: int
    raw_payload_count: int
    price_point_count: int
    book_snapshot_count: int
    best_bid_ask_count: int
    last_trade_count: int
    events: list[BackfillEvent] = field(default_factory=list)


class TokenSelector(Protocol):
    def select_top_tokens(self) -> list[ReferenceToken]: ...


class ClobBackfillClient(Protocol):
    def fetch_prices_history_batch(
        self,
        markets: list[str],
        start_ts: int | None = None,
        end_ts: int | None = None,
        interval: str = "1d",
        fidelity: int = 1,
    ) -> dict[str, Any]: ...

    def fetch_order_books(self, token_ids: list[str]) -> list[dict[str, Any]]: ...


class MarketDataBackfillService:
    def __init__(
        self,
        selector: TokenSelector,
        clob_client: ClobBackfillClient,
        store: MarketDataStore,
        price_history_chunk_size: int = 20,
        book_chunk_size: int = 100,
        interval: str = "1d",
        fidelity: int = 1,
    ) -> None:
        self.selector = selector
        self.clob_client = clob_client
        self.store = store
        self.price_history_chunk_size = price_history_chunk_size
        self.book_chunk_size = book_chunk_size
        self.interval = interval
        self.fidelity = fidelity

    def backfill_top_tokens(
        self,
        start_ts: int | None = None,
        end_ts: int | None = None,
        gap_fill: bool = False,
        upsert_reference: bool = True,
    ) -> BackfillResult:
        events = [
            _event("Backfill started", "System", "running", "REST backfill started")
        ]
        self.store.init_schema()
        tokens = self.selector.select_top_tokens()
        if upsert_reference:
            self.store.upsert_reference_tokens(tokens)
        token_by_id = {token.token_id: token for token in tokens}

        raw_payload_count = 0
        price_points: list[PriceHistoryPoint] = []
        for token_chunk in _chunks(tokens, self.price_history_chunk_size):
            token_ids = [token.token_id for token in token_chunk]
            payload = self.clob_client.fetch_prices_history_batch(
                token_ids,
                start_ts=start_ts,
                end_ts=end_ts,
                interval=self.interval,
                fidelity=self.fidelity,
            )
            self.store.insert_raw_rest_payload(
                RawPayloadEnvelope(
                    source="CLOB_REST",
                    endpoint="/batch-prices-history",
                    payload=payload,
                    received_at=utc_now(),
                    gap_fill=gap_fill,
                )
            )
            raw_payload_count += 1
            price_points.extend(
                _normalize_price_history(payload, token_by_id, gap_fill=gap_fill)
            )

        price_point_count = self.store.upsert_price_history_points(price_points)

        snapshots: list[BookSnapshot] = []
        bbo_rows: list[BestBidAsk] = []
        last_trades: list[LastTrade] = []
        for token_chunk in _chunks(tokens, self.book_chunk_size):
            token_ids = [token.token_id for token in token_chunk]
            books = self.clob_client.fetch_order_books(token_ids)
            self.store.insert_raw_rest_payload(
                RawPayloadEnvelope(
                    source="CLOB_REST",
                    endpoint="/books",
                    payload=books,
                    received_at=utc_now(),
                    gap_fill=gap_fill,
                )
            )
            raw_payload_count += 1
            for book in books:
                normalized = _normalize_book(book, token_by_id, gap_fill=gap_fill)
                if normalized is None:
                    continue
                snapshot, bbo, last_trade = normalized
                self.store.insert_book_snapshot(snapshot)
                snapshots.append(snapshot)
                if bbo is not None:
                    bbo_rows.append(bbo)
                if last_trade is not None:
                    last_trades.append(last_trade)

        bbo_count = self.store.upsert_best_bid_ask(bbo_rows)
        last_trade_count = self.store.upsert_last_trades(last_trades)
        events.append(
            _event(
                "Backfill completed",
                "System",
                "success",
                f"Backfilled {len(tokens)} tokens",
                gap_fill=gap_fill,
            )
        )
        return BackfillResult(
            selected_count=len(tokens),
            raw_payload_count=raw_payload_count,
            price_point_count=price_point_count,
            book_snapshot_count=len(snapshots),
            best_bid_ask_count=bbo_count,
            last_trade_count=last_trade_count,
            events=events,
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _event(
    step: str,
    source: str,
    status: str,
    message: str,
    token_id: str | None = None,
    gap_fill: bool = False,
) -> BackfillEvent:
    return BackfillEvent(
        timestamp=utc_now(),
        step=step,
        source=source,
        status=status,
        message=message,
        token_id=token_id,
        gap_fill=gap_fill,
    )


def _chunks(values: list[ReferenceToken], size: int) -> Iterable[list[ReferenceToken]]:
    if size < 1:
        raise ValueError("chunk size must be at least 1")
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _normalize_price_history(
    payload: dict[str, Any],
    token_by_id: dict[str, ReferenceToken],
    gap_fill: bool,
) -> list[PriceHistoryPoint]:
    history = payload.get("history", payload)
    if not isinstance(history, dict):
        return []
    points: list[PriceHistoryPoint] = []
    for token_id, token_history in history.items():
        token = token_by_id.get(str(token_id))
        if token is None or not isinstance(token_history, list):
            continue
        for point in token_history:
            if not isinstance(point, dict) or "t" not in point or "p" not in point:
                continue
            points.append(
                PriceHistoryPoint(
                    token_id=token.token_id,
                    condition_id=token.condition_id,
                    price=Decimal(str(point["p"])),
                    source_ts=datetime.fromtimestamp(int(point["t"]), timezone.utc),
                    received_at=utc_now(),
                    gap_fill=gap_fill,
                )
            )
    return points


def _normalize_book(
    book: dict[str, Any],
    token_by_id: dict[str, ReferenceToken],
    gap_fill: bool,
) -> tuple[BookSnapshot, BestBidAsk | None, LastTrade | None] | None:
    token_id = str(book.get("asset_id") or book.get("token_id") or "")
    token = token_by_id.get(token_id)
    if token is None:
        return None

    bids = [
        BookLevel(side="BUY", price=Decimal(str(row["price"])), size=Decimal(str(row["size"])))
        for row in book.get("bids", [])
        if "price" in row and "size" in row
    ]
    asks = [
        BookLevel(side="SELL", price=Decimal(str(row["price"])), size=Decimal(str(row["size"])))
        for row in book.get("asks", [])
        if "price" in row and "size" in row
    ]
    source_ts = _parse_source_ts(book.get("timestamp"))
    snapshot = BookSnapshot(
        token_id=token.token_id,
        condition_id=token.condition_id or book.get("market"),
        market=book.get("market"),
        source_ts=source_ts,
        received_at=utc_now(),
        source="CLOB_REST",
        hash=book.get("hash"),
        bids=bids,
        asks=asks,
        min_order_size=_optional_decimal(book.get("min_order_size")),
        tick_size=_optional_decimal(book.get("tick_size")),
        neg_risk=book.get("neg_risk"),
        last_trade_price=_optional_decimal(book.get("last_trade_price")),
        gap_fill=gap_fill,
    )
    bbo = _best_bid_ask(token, bids, asks, source_ts, gap_fill)
    last_trade = None
    if snapshot.last_trade_price is not None:
        last_trade = LastTrade(
            token_id=token.token_id,
            condition_id=token.condition_id,
            price=snapshot.last_trade_price,
            source_ts=source_ts,
            received_at=utc_now(),
            source="CLOB_REST",
            gap_fill=gap_fill,
        )
    return snapshot, bbo, last_trade


def _best_bid_ask(
    token: ReferenceToken,
    bids: list[BookLevel],
    asks: list[BookLevel],
    source_ts: datetime | None,
    gap_fill: bool,
) -> BestBidAsk | None:
    best_bid = max((bid.price for bid in bids), default=None)
    best_ask = min((ask.price for ask in asks), default=None)
    spread = best_ask - best_bid if best_bid is not None and best_ask is not None else None
    midpoint = (
        (best_ask + best_bid) / Decimal("2")
        if best_bid is not None and best_ask is not None
        else None
    )
    if best_bid is None and best_ask is None:
        return None
    return BestBidAsk(
        token_id=token.token_id,
        condition_id=token.condition_id,
        best_bid=best_bid,
        best_ask=best_ask,
        spread=spread,
        midpoint=midpoint,
        source_ts=source_ts,
        received_at=utc_now(),
        source="Normalized",
        gap_fill=gap_fill,
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


def main() -> None:
    top_n = int(os.getenv("POLYMARKET_TOP_N", "50"))
    market_store = MarketStore(Path("data/markets.sqlite3"))
    store = MarketDataStore()
    selector = UniverseSelector(market_store, top_n=top_n)
    service = MarketDataBackfillService(selector, ClobClient(), store)
    result = service.backfill_top_tokens()
    print(
        "Backfilled "
        f"{result.selected_count} tokens, {result.price_point_count} price points, "
        f"{result.book_snapshot_count} book snapshots"
    )


if __name__ == "__main__":
    main()
