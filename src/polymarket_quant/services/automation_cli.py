from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from polymarket_quant.adapters.polymarket import ClobClient, GammaClient
from polymarket_quant.domain.automation import AutomationResolvedConfig, AutomationStrategyDefinition
from polymarket_quant.domain.market_data import utc_now
from polymarket_quant.domain.operator import GlobalMode
from polymarket_quant.domain.strategy import RunMode, StrategyEvent, StrategyEventType
from polymarket_quant.services.automation_config import load_automation_config
from polymarket_quant.services.automation_runner import AutomationRunResult, AutomationRunner
from polymarket_quant.services.automation_tasks import load_object
from polymarket_quant.services.dashboard_snapshot import DashboardSnapshotService
from polymarket_quant.services.fill_engine import FillEngineConfig
from polymarket_quant.services.market_sync import MarketSyncService
from polymarket_quant.services.market_display import MarketDisplayService
from polymarket_quant.services.operator_queries import OperatorQueryService
from polymarket_quant.services.operator_runtime_registry import OperatorRuntimeRegistry
from polymarket_quant.services.paper_exchange import PaperExchangeService
from polymarket_quant.services.strategy_cli import StrategyCliService
from polymarket_quant.storage.market_store import MarketStore
from polymarket_quant.storage.market_data_store import DATABASE_URL_ENV, MarketDataStore
from polymarket_quant.strategy.base import BaseStrategy
from polymarket_quant.strategy.scheduled import PROFILE_CONFIGS, StressProfile


class AutomationCliService:
    def __init__(
        self,
        *,
        git_commit: str = "workspace",
        runner_factory: Any | None = None,
    ) -> None:
        self.git_commit = git_commit
        self.runner_factory = runner_factory

    def run(self, config_path: str | Path) -> AutomationRunResult:
        resolved_config = load_automation_config(config_path)
        return self.run_resolved(resolved_config)

    def run_resolved(self, resolved_config: AutomationResolvedConfig) -> AutomationRunResult:
        runtime_registry = OperatorRuntimeRegistry(
            global_mode=_global_mode_for_automation(resolved_config.mode)
        )
        runner = (
            self.runner_factory(resolved_config)
            if self.runner_factory is not None
            else AutomationRunner(
                sync_callable=self._build_market_sync_callable(resolved_config.market_store_path),
                strategy_executor=lambda strategy: self._execute_strategy(
                    strategy,
                    market_store_path=resolved_config.market_store_path,
                    artifact_root=resolved_config.artifact_root,
                    runtime_registry=runtime_registry,
                ),
                query_service_factory=lambda config: OperatorQueryService(
                    config.artifact_root,
                    runtime_registry=runtime_registry,
                ),
            )
        )
        result = runner.run(resolved_config)
        self._write_dashboard_snapshot(resolved_config, result)
        return result

    def _build_market_sync_callable(self, market_store_path: str):
        def _sync() -> Any:
            service = MarketSyncService(
                gamma_client=GammaClient(),
                clob_client=ClobClient(),
                store=MarketStore(market_store_path),
            )
            return service.sync_once()

        return _sync

    def _write_dashboard_snapshot(
        self,
        resolved_config: AutomationResolvedConfig,
        result: AutomationRunResult,
    ) -> None:
        runtime_root = Path(str(resolved_config.metadata.get("runtime_root", "data/runtime")))
        query_service = OperatorQueryService(resolved_config.artifact_root)
        DashboardSnapshotService(
            query_service,
            snapshot_path=runtime_root / "latest_snapshot.json",
            market_display_service=MarketDisplayService(
                market_store=MarketStore(resolved_config.market_store_path),
                query_service=query_service,
                market_data_store=MarketDataStore()
                if os.getenv(DATABASE_URL_ENV)
                else None,
            ),
        ).write_latest(automation_run=result.automation_run)

    def _execute_strategy(
        self,
        strategy_definition: AutomationStrategyDefinition,
        *,
        market_store_path: str,
        artifact_root: str,
        runtime_registry: OperatorRuntimeRegistry,
    ) -> Any:
        strategy_class = load_object(strategy_definition.strategy_class)
        strategy = strategy_class()
        if not isinstance(strategy, BaseStrategy):
            raise TypeError("strategy_class must instantiate BaseStrategy")
        cli = StrategyCliService(
            artifact_root,
            git_commit=self.git_commit,
            runtime_registry=runtime_registry,
        )
        raw_config = cli.load_config(strategy_definition.config_path)
        prepared_config = prepare_strategy_raw_config(
            raw_config,
            market_store=MarketStore(market_store_path),
            clob_client=ClobClient(),
        )
        prepared_config = assign_unique_strategy_run_id(
            prepared_config,
            strategy_name=strategy_definition.name,
        )
        events = build_bootstrap_market_events(
            prepared_config,
            clob_client=ClobClient(),
        )
        return cli.run_from_config(
            strategy,
            prepared_config,
            events=events,
            paper_exchange=PaperExchangeService(
                fill_config=FillEngineConfig(submit_latency_ms=0, cancel_latency_ms=0)
            ),
        )


def prepare_strategy_raw_config(
    raw_config: dict[str, Any],
    *,
    market_store: MarketStore,
    clob_client: ClobClient | None = None,
) -> dict[str, Any]:
    prepared = dict(raw_config)
    universe = dict(raw_config.get("universe", {}))
    token_ids = [str(token_id) for token_id in universe.get("token_ids", []) if str(token_id)]
    token_mappings = [
        mapping for mapping in universe.get("token_mappings", []) if isinstance(mapping, dict)
    ]
    if token_ids and token_mappings:
        prepared["universe"] = universe
        return prepared

    selected_candidates = _select_default_markets(
        market_store,
        clob_client=clob_client,
        universe_config=universe,
    )
    if not selected_candidates:
        prepared["universe"] = universe
        return prepared

    universe.setdefault("dataset_id", "automation-market-store")
    universe["token_ids"] = [token_id for _market, token_id in selected_candidates]
    universe["token_mappings"] = [
        {
            "market_id": market.market_id,
            "condition_id": market.condition_id,
            "token_id": token_id,
            "question": market.question,
            "category": market.category,
            "end_date": market.end_date.isoformat() if market.end_date else None,
            "liquidity": market.liquidity,
        }
        for market, token_id in selected_candidates
    ]
    prepared["universe"] = universe
    return prepared


def assign_unique_strategy_run_id(
    raw_config: dict[str, Any],
    *,
    strategy_name: str,
    now: datetime | None = None,
    suffix: str | None = None,
) -> dict[str, Any]:
    prepared = dict(raw_config)
    base_run_id = str(prepared.get("run_id") or strategy_name or "strategy-run").strip()
    timestamp = (now or utc_now()).strftime("%Y%m%dT%H%M%SZ")
    unique_suffix = suffix or uuid4().hex[:8]
    prepared["run_id"] = f"{_slug_run_id(base_run_id)}-{timestamp}-{unique_suffix}"
    return prepared


def build_bootstrap_market_events(
    raw_config: dict[str, Any],
    *,
    clob_client: ClobClient,
    now: datetime | None = None,
) -> list[StrategyEvent]:
    universe = dict(raw_config.get("universe", {}))
    token_ids = [str(token_id) for token_id in universe.get("token_ids", []) if str(token_id)]
    token_mapping_by_id = {
        str(mapping.get("token_id")): dict(mapping)
        for mapping in universe.get("token_mappings", [])
        if isinstance(mapping, dict) and mapping.get("token_id")
    }
    if not token_ids:
        return []

    timestamp = now or utc_now()
    try:
        books = clob_client.fetch_order_books(token_ids)
    except Exception:
        books = []
    books_by_token = {
        str(book.get("asset_id") or book.get("token_id") or ""): book for book in books
    }
    staged_offsets = _bootstrap_stage_offsets(raw_config)
    events: list[StrategyEvent] = []
    for token_id in token_ids:
        mapping = token_mapping_by_id.get(token_id, {})
        base_payload = _market_payload_from_book(
            token_id,
            mapping,
            books_by_token.get(token_id),
        )
        condition_id = str(
            mapping.get("condition_id") or base_payload.get("condition_id") or ""
        )
        for stage_index, offset_seconds in enumerate(staged_offsets):
            stage_timestamp = timestamp + timedelta(seconds=offset_seconds)
            market_payload = _stage_market_payload(base_payload, stage_index=stage_index)
            events.append(
                StrategyEvent(
                    event_type=StrategyEventType.MARKET,
                    ts=stage_timestamp,
                    token_id=token_id,
                    condition_id=condition_id,
                    source="automation.bootstrap",
                    payload={"by_token": {token_id: market_payload}},
                )
            )
    return events


def _market_payload_from_book(
    token_id: str,
    mapping: dict[str, Any],
    book: dict[str, Any] | None,
) -> dict[str, Any]:
    if book is None:
        return {
            "token_id": token_id,
            "condition_id": mapping.get("condition_id"),
            "market_id": mapping.get("market_id"),
            "best_bid": Decimal("0.49"),
            "best_ask": Decimal("0.51"),
            "midpoint": Decimal("0.50"),
            "last_trade_price": Decimal("0.50"),
            "tick_size": Decimal("0.01"),
            "min_order_size": Decimal("1"),
            "active": True,
            "accepting_orders": True,
            "book_source": "synthetic_fallback",
        }

    book_levels = _book_levels_from_book(book)
    best_bid = (
        max((level["price"] for level in book_levels["bids"]), default=None)
        if book_levels["bids"]
        else None
    )
    best_ask = (
        min((level["price"] for level in book_levels["asks"]), default=None)
        if book_levels["asks"]
        else None
    )
    midpoint = (
        (best_bid + best_ask) / Decimal("2")
        if best_bid is not None and best_ask is not None
        else best_ask or best_bid or Decimal("0.50")
    )
    return {
        "token_id": token_id,
        "condition_id": mapping.get("condition_id") or book.get("market"),
        "market_id": mapping.get("market_id") or book.get("market"),
        "best_bid": best_bid,
        "best_ask": best_ask,
        "midpoint": midpoint,
        "last_trade_price": _optional_decimal(book.get("last_trade_price")) or midpoint,
        "tick_size": _optional_decimal(book.get("tick_size")) or Decimal("0.01"),
        "min_order_size": _optional_decimal(book.get("min_order_size")) or Decimal("1"),
        "active": True,
        "accepting_orders": True,
        "book_source": "clob" if book_levels["bids"] and book_levels["asks"] else "clob_incomplete",
        "book_levels": book_levels,
    }


def _optional_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _book_levels_from_book(book: dict[str, Any]) -> dict[str, list[dict[str, Decimal | str]]]:
    return {
        "bids": sorted(
            _book_side_levels(book.get("bids"), side="BUY"),
            key=lambda level: Decimal(str(level["price"])),
            reverse=True,
        ),
        "asks": sorted(
            _book_side_levels(book.get("asks"), side="SELL"),
            key=lambda level: Decimal(str(level["price"])),
        ),
    }


def _book_side_levels(
    rows: Any,
    *,
    side: str,
) -> list[dict[str, Decimal | str]]:
    if not isinstance(rows, list):
        return []
    levels: list[dict[str, Decimal | str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        price = _optional_decimal(row.get("price"))
        size = _optional_decimal(row.get("size"))
        if price is None or size is None or size <= 0:
            continue
        levels.append({"side": side, "price": price, "size": size})
    return levels


def _select_default_markets(
    market_store: MarketStore,
    *,
    clob_client: ClobClient | None = None,
    universe_config: dict[str, Any] | None = None,
) -> list[tuple[Any, str]]:
    universe_config = dict(universe_config or {})
    markets = market_store.list_markets()
    if not markets:
        return []
    max_tokens = max(1, int(universe_config.get("max_tokens", 1)))
    if str(universe_config.get("selection_mode", "")).lower() == "near_expiry":
        return _select_near_expiry_markets(
            markets,
            clob_client=clob_client,
            max_tokens=max_tokens,
            universe_config=universe_config,
        )
    if clob_client is None:
        return [(markets[0], str(markets[0].yes_token_id))]
    candidate_markets = markets[:25]
    ranked = _rank_market_tokens(candidate_markets, clob_client=clob_client)
    return _dedupe_market_rows(ranked, max_tokens=max_tokens)


def _select_near_expiry_markets(
    markets: list[Any],
    *,
    clob_client: ClobClient | None,
    max_tokens: int,
    universe_config: dict[str, Any],
) -> list[tuple[Any, str]]:
    now = utc_now()
    min_minutes = int(universe_config.get("min_minutes_to_expiry", 15))
    max_hours = universe_config.get("max_hours_to_expiry")
    candidate_limit = max(1, int(universe_config.get("candidate_limit", 75)))
    min_book_score = int(universe_config.get("min_book_score", 3))
    min_end_date = now + timedelta(minutes=min_minutes)
    max_end_date = None if max_hours is None else now + timedelta(hours=int(max_hours))
    candidates = [
        market
        for market in markets
        if market.end_date is not None
        and market.end_date >= min_end_date
        and (max_end_date is None or market.end_date <= max_end_date)
    ]
    if not candidates:
        candidates = [
            market
            for market in markets
            if market.end_date is not None and market.end_date >= min_end_date
        ]
    candidates.sort(
        key=lambda market: (
            market.end_date,
            -(market.liquidity or 0.0),
            market.question,
        )
    )
    candidates = candidates[:candidate_limit]
    if clob_client is None:
        return [
            (market, str(market.yes_token_id))
            for market in candidates[:max_tokens]
            if market.yes_token_id
        ]

    ranked = _rank_market_tokens(candidates, clob_client=clob_client)
    eligible = [
        row
        for row in ranked
        if row[0] >= min_book_score
    ]
    rows = eligible or ranked
    rows.sort(
        key=lambda row: (
            row[2].end_date,
            -row[0],
            -row[1],
            row[2].question,
        )
    )
    return _dedupe_market_rows(rows, max_tokens=max_tokens)


def _rank_market_tokens(
    candidate_markets: list[Any],
    *,
    clob_client: ClobClient,
) -> list[tuple[int, float, Any, str]]:
    token_ids = [
        token_id
        for market in candidate_markets
        for token_id in (market.yes_token_id, market.no_token_id)
        if token_id
    ]
    if not token_ids:
        return []
    try:
        books = clob_client.fetch_order_books(token_ids)
    except Exception:
        books = []
    books_by_token = {
        str(book.get("asset_id") or book.get("token_id") or ""): book for book in books
    }
    ranked_candidates: list[tuple[int, float, Any, str]] = []
    for market in candidate_markets:
        for token_id in (market.yes_token_id, market.no_token_id):
            book = books_by_token.get(str(token_id))
            score = _score_bootstrap_market(book)
            ranked_candidates.append((score, market.liquidity or 0.0, market, str(token_id)))
    ranked_candidates.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return ranked_candidates


def _dedupe_market_rows(
    rows: list[tuple[int, float, Any, str]],
    *,
    max_tokens: int,
) -> list[tuple[Any, str]]:
    selected: list[tuple[Any, str]] = []
    seen_markets: set[str] = set()
    for _score, _liquidity, market, token_id in rows:
        market_key = str(market.condition_id or market.market_id or token_id)
        if market_key in seen_markets:
            continue
        selected.append((market, token_id))
        seen_markets.add(market_key)
        if len(selected) >= max_tokens:
            break
    return selected


def _bootstrap_stage_offsets(raw_config: dict[str, Any]) -> list[int]:
    strategy_config = dict(raw_config.get("strategy", {}))
    profile_value = strategy_config.get("stress_profile")
    if not profile_value:
        return [0]
    profile = StressProfile(str(profile_value))
    profile_config = PROFILE_CONFIGS[profile]
    stage_interval_seconds = int(
        strategy_config.get(
            "stress_stage_interval_seconds",
            profile_config.stage_interval_seconds,
        )
    )
    return [index * stage_interval_seconds for index in range(len(profile_config.stages))]


def _stage_market_payload(
    base_payload: dict[str, Any],
    *,
    stage_index: int,
) -> dict[str, Any]:
    payload = dict(base_payload)
    tick_size = _optional_decimal(payload.get("tick_size")) or Decimal("0.01")
    midpoint = _optional_decimal(payload.get("midpoint")) or Decimal("0.50")
    real_best_bid = _optional_decimal(payload.get("best_bid"))
    real_best_ask = _optional_decimal(payload.get("best_ask"))
    real_book_levels = payload.get("book_levels")
    deltas = [
        Decimal("0"),
        tick_size,
        tick_size * Decimal("-1"),
        tick_size * Decimal("-2"),
        tick_size * Decimal("1"),
    ]
    delta = deltas[min(stage_index, len(deltas) - 1)]
    if (
        payload.get("book_source") == "clob"
        and isinstance(real_book_levels, dict)
        and real_best_bid is not None
        and real_best_ask is not None
    ):
        staged_last_trade = max(
            Decimal("0.01"),
            min(Decimal("0.99"), midpoint + delta),
        )
        payload.update(
            {
                "best_bid": real_best_bid,
                "best_ask": real_best_ask,
                "midpoint": (real_best_bid + real_best_ask) / Decimal("2"),
                "last_trade_price": staged_last_trade,
                "bootstrap_stage": stage_index,
                "book_source": "clob_augmented",
                "book_levels": _stage_real_book_levels(
                    real_book_levels,
                    stage_index=stage_index,
                    best_bid=real_best_bid,
                    best_ask=real_best_ask,
                ),
            }
        )
        return payload

    staged_midpoint = max(Decimal("0.01"), min(Decimal("0.99"), midpoint + delta))
    half_spread = max(
        tick_size,
        (_optional_decimal(payload.get("best_ask")) or staged_midpoint)
        - (_optional_decimal(payload.get("best_bid")) or staged_midpoint),
    )
    if half_spread <= 0:
        half_spread = tick_size * Decimal("2")
    best_bid = _align_price(
        max(Decimal("0.01"), staged_midpoint - (half_spread / Decimal("2"))),
        tick_size,
        direction="down",
    )
    best_ask = _align_price(
        min(Decimal("0.99"), staged_midpoint + (half_spread / Decimal("2"))),
        tick_size,
        direction="up",
    )
    if best_ask <= best_bid:
        best_ask = _align_price(
            min(Decimal("0.99"), best_bid + tick_size),
            tick_size,
            direction="up",
        )
    payload.update(
        {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "midpoint": (best_bid + best_ask) / Decimal("2"),
            "last_trade_price": staged_midpoint,
            "bootstrap_stage": stage_index,
            "book_source": "synthetic_staged",
            "book_levels": _stage_book_levels(
                stage_index=stage_index,
                best_bid=best_bid,
                best_ask=best_ask,
                tick_size=tick_size,
            ),
        }
    )
    return payload


def _score_bootstrap_market(book: dict[str, Any] | None) -> int:
    if book is None:
        return 0
    midpoint = _book_midpoint(book)
    if midpoint is None:
        return 1
    has_both_sides = bool(book.get("bids")) and bool(book.get("asks"))
    if Decimal("0.20") <= midpoint <= Decimal("0.80"):
        midpoint_score = 3
    elif Decimal("0.80") < midpoint <= Decimal("0.99"):
        midpoint_score = 2
    elif Decimal("0.05") <= midpoint < Decimal("0.20"):
        midpoint_score = 1
    else:
        midpoint_score = 0
    return midpoint_score + (2 if has_both_sides else 0)


def _book_midpoint(book: dict[str, Any]) -> Decimal | None:
    bids = [
        Decimal(str(row["price"]))
        for row in book.get("bids", [])
        if isinstance(row, dict) and "price" in row
    ]
    asks = [
        Decimal(str(row["price"]))
        for row in book.get("asks", [])
        if isinstance(row, dict) and "price" in row
    ]
    if bids and asks:
        return (max(bids) + min(asks)) / Decimal("2")
    return _optional_decimal(book.get("last_trade_price"))


def _stage_book_levels(
    *,
    stage_index: int,
    best_bid: Decimal,
    best_ask: Decimal,
    tick_size: Decimal,
) -> dict[str, list[dict[str, Decimal | str]]]:
    depth_notional = _stage_depth_notional(stage_index)
    bid_size = _depth_size(depth_notional, best_bid)
    ask_size = _depth_size(depth_notional, best_ask)
    return {
        "bids": [
            {"side": "BUY", "price": best_bid, "size": bid_size},
            {
                "side": "BUY",
                "price": max(Decimal("0.01"), best_bid - tick_size),
                "size": bid_size,
            },
        ],
        "asks": [
            {"side": "SELL", "price": best_ask, "size": ask_size},
            {
                "side": "SELL",
                "price": min(Decimal("0.99"), best_ask + tick_size),
                "size": ask_size,
            },
        ],
    }


def _stage_real_book_levels(
    book_levels: dict[str, Any],
    *,
    stage_index: int,
    best_bid: Decimal,
    best_ask: Decimal,
) -> dict[str, list[dict[str, Decimal | str]]]:
    levels = {
        "bids": _copy_book_levels(book_levels.get("bids"), side="BUY"),
        "asks": _copy_book_levels(book_levels.get("asks"), side="SELL"),
    }
    depth_notional = _stage_depth_notional(stage_index)
    _ensure_top_depth(
        levels["bids"],
        side="BUY",
        price=best_bid,
        depth_notional=depth_notional,
    )
    _ensure_top_depth(
        levels["asks"],
        side="SELL",
        price=best_ask,
        depth_notional=depth_notional,
    )
    levels["bids"].sort(key=lambda level: Decimal(str(level["price"])), reverse=True)
    levels["asks"].sort(key=lambda level: Decimal(str(level["price"])))
    return levels


def _copy_book_levels(rows: Any, *, side: str) -> list[dict[str, Decimal | str]]:
    if not isinstance(rows, list):
        return []
    copied: list[dict[str, Decimal | str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        price = _optional_decimal(row.get("price"))
        size = _optional_decimal(row.get("size"))
        if price is None or size is None or size <= 0:
            continue
        copied.append({"side": str(row.get("side") or side), "price": price, "size": size})
    return copied


def _ensure_top_depth(
    levels: list[dict[str, Decimal | str]],
    *,
    side: str,
    price: Decimal,
    depth_notional: Decimal,
) -> None:
    required_size = _depth_size(depth_notional, price)
    for level in levels:
        if _optional_decimal(level.get("price")) == price:
            current_size = _optional_decimal(level.get("size")) or Decimal("0")
            if current_size < required_size:
                level["size"] = required_size
            return
    levels.append({"side": side, "price": price, "size": required_size})


def _stage_depth_notional(stage_index: int) -> Decimal:
    notional_by_stage = [
        Decimal("250"),
        Decimal("300"),
        Decimal("350"),
        Decimal("300"),
        Decimal("250"),
    ]
    return notional_by_stage[min(stage_index, len(notional_by_stage) - 1)]


def _align_price(value: Decimal, tick_size: Decimal, *, direction: str) -> Decimal:
    if tick_size <= 0:
        return value
    units = value / tick_size
    if direction == "down":
        rounded_units = units.to_integral_value(rounding=ROUND_FLOOR)
    else:
        rounded_units = units.to_integral_value(rounding=ROUND_CEILING)
    return rounded_units * tick_size


def _depth_size(depth_notional: Decimal, price: Decimal) -> Decimal:
    if price <= 0:
        return depth_notional
    return depth_notional / price


def _slug_run_id(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned or "strategy-run"


def _global_mode_for_automation(mode: RunMode) -> GlobalMode:
    if mode == RunMode.REALTIME_PAPER:
        return GlobalMode.PAPER
    return GlobalMode.REPLAY


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Phase 6 automation job.")
    parser.add_argument("config_path", help="Path to the automation YAML/JSON config")
    parser.add_argument(
        "--git-commit",
        default="workspace",
        help="Git commit string to persist into strategy artifacts",
    )
    args = parser.parse_args(argv)

    result = AutomationCliService(git_commit=args.git_commit).run(args.config_path)
    print(f"automation_run_id={result.automation_run.run_id}")
    print(f"automation_run_dir={result.run_directory}")
    if result.report is not None:
        print(f"markdown_report={result.report.markdown_path}")
        if result.report.html_path:
            print(f"html_report={result.report.html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
