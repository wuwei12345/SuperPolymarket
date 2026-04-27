from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Any

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

    selected_candidate = _select_default_market(market_store, clob_client=clob_client)
    if selected_candidate is None:
        prepared["universe"] = universe
        return prepared
    selected_market, selected_token_id = selected_candidate

    universe.setdefault("dataset_id", "automation-market-store")
    universe["token_ids"] = [selected_token_id]
    universe["token_mappings"] = [
        {
            "market_id": selected_market.market_id,
            "condition_id": selected_market.condition_id,
            "token_id": selected_token_id,
            "question": selected_market.question,
            "category": selected_market.category,
        }
    ]
    prepared["universe"] = universe
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
        }

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
    best_bid = max(bids) if bids else None
    best_ask = min(asks) if asks else None
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
    }


def _optional_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _select_default_market(
    market_store: MarketStore,
    *,
    clob_client: ClobClient | None = None,
):
    markets = market_store.list_markets()
    if not markets:
        return None
    if clob_client is None:
        return markets[0], str(markets[0].yes_token_id)
    candidate_markets = markets[:25]
    token_ids = [
        token_id
        for market in candidate_markets
        for token_id in (market.yes_token_id, market.no_token_id)
        if token_id
    ]
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
    best = ranked_candidates[0]
    return best[2], best[3]


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
    deltas = [
        Decimal("0"),
        tick_size * Decimal("2"),
        tick_size * Decimal("-1"),
        tick_size * Decimal("-3"),
        tick_size * Decimal("1"),
    ]
    delta = deltas[min(stage_index, len(deltas) - 1)]
    staged_midpoint = max(Decimal("0.01"), min(Decimal("0.99"), midpoint + delta))
    half_spread = max(tick_size, (_optional_decimal(payload.get("best_ask")) or staged_midpoint) - (_optional_decimal(payload.get("best_bid")) or staged_midpoint))
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
    size_by_stage = [
        Decimal("250"),
        Decimal("250"),
        Decimal("300"),
        Decimal("300"),
        Decimal("200"),
    ]
    size = size_by_stage[min(stage_index, len(size_by_stage) - 1)]
    return {
        "bids": [
            {"side": "BUY", "price": best_bid, "size": size},
            {
                "side": "BUY",
                "price": max(Decimal("0.01"), best_bid - tick_size),
                "size": size,
            },
        ],
        "asks": [
            {"side": "SELL", "price": best_ask, "size": size},
            {
                "side": "SELL",
                "price": min(Decimal("0.99"), best_ask + tick_size),
                "size": size,
            },
        ],
    }


def _align_price(value: Decimal, tick_size: Decimal, *, direction: str) -> Decimal:
    if tick_size <= 0:
        return value
    units = value / tick_size
    if direction == "down":
        rounded_units = units.to_integral_value(rounding=ROUND_FLOOR)
    else:
        rounded_units = units.to_integral_value(rounding=ROUND_CEILING)
    return rounded_units * tick_size
    return markets[0]


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
