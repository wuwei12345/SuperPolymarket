from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from polymarket_quant.domain.operator import (
    GlobalMode,
    LocalRunMode,
    NewOrderBlockState,
    StrategyRuntimeState,
)
from polymarket_quant.domain.market_data import BookLevel, BookSnapshot, utc_now
from polymarket_quant.domain.strategy import (
    ResolvedRunConfig,
    RunManifest,
    RunMode,
    StrategyEvent,
    StrategySignal,
    UniverseSnapshot,
)
from polymarket_quant.services.experiment_metrics import ExperimentMetricsService
from polymarket_quant.services.operator_runtime_registry import OperatorRuntimeRegistry
from polymarket_quant.services.order_risk import MarketConstraints, RiskLimits
from polymarket_quant.services.paper_exchange import PaperExchangeService
from polymarket_quant.services.realtime_strategy_runner import (
    RealtimeExecutionResult,
    RealtimeStrategyRunner,
)
from polymarket_quant.services.replay_runtime import ReplayRuntime
from polymarket_quant.services.run_artifacts import RunArtifactBundleWriter
from polymarket_quant.services.signal_execution import SignalExecutionService
from polymarket_quant.services.strategy_runtime import StrategyRuntime
from polymarket_quant.strategy.base import BaseStrategy


ConstraintsProvider = Callable[[StrategySignal], MarketConstraints]
LimitsProvider = Callable[[StrategySignal], RiskLimits]
SnapshotProvider = Callable[[StrategySignal], BookSnapshot | None]


class StrategyCliRunResult:
    def __init__(
        self,
        manifest: RunManifest,
        run_directory: Path,
        metrics_summary: dict[str, Any],
    ) -> None:
        self.manifest = manifest
        self.run_directory = run_directory
        self.metrics_summary = metrics_summary


class StrategyCliService:
    def __init__(
        self,
        artifact_root: str | Path,
        *,
        metrics_service: ExperimentMetricsService | None = None,
        git_commit: str = "workspace",
        runtime_registry: OperatorRuntimeRegistry | None = None,
    ) -> None:
        self.artifact_root = Path(artifact_root)
        self.metrics_service = metrics_service or ExperimentMetricsService()
        self.git_commit = git_commit
        self.runtime_registry = runtime_registry

    def load_config(self, path: str | Path) -> dict[str, Any]:
        config_path = Path(path)
        text = config_path.read_text()
        if config_path.suffix.lower() in {".yaml", ".yml"}:
            loaded = yaml.safe_load(text) or {}
        elif config_path.suffix.lower() == ".json":
            loaded = json.loads(text)
        else:
            raise ValueError("config path must be YAML or JSON")
        if not isinstance(loaded, dict):
            raise ValueError("config must deserialize into an object")
        return loaded

    def resolve_config(
        self, raw_config: dict[str, Any], *, strategy_name: str | None = None
    ) -> ResolvedRunConfig:
        raw_strategy = _mapping(raw_config.get("strategy"))
        resolved_strategy = {
            "name": strategy_name or raw_strategy.get("name", "strategy"),
            "version": raw_strategy.get("version", "dev"),
            **raw_strategy,
        }
        resolved_execution = {
            "time_in_force": "GTC",
            "post_only": False,
            **_mapping(raw_config.get("execution")),
        }
        resolved_sizing = {
            "target_exposure_mode": "fraction_of_equity",
            **_mapping(raw_config.get("sizing")),
        }
        mode = RunMode(raw_config.get("mode", RunMode.RESEARCH))
        step_interval = raw_config.get("step_interval")
        if step_interval is None:
            step_interval = _mapping(raw_config.get("replay")).get("step_interval")

        return ResolvedRunConfig(
            strategy=resolved_strategy,
            universe=_mapping(raw_config.get("universe")),
            sizing=resolved_sizing,
            execution=resolved_execution,
            risk=_mapping(raw_config.get("risk")),
            data_sources=_mapping(raw_config.get("data_sources")),
            mode=mode,
            replay=_mapping(raw_config.get("replay")),
            realtime=_mapping(raw_config.get("realtime")),
            step_interval=step_interval,
        )

    def run(
        self,
        strategy: BaseStrategy,
        config_path: str | Path,
        *,
        events: Sequence[StrategyEvent] = (),
        constraints_provider: ConstraintsProvider | None = None,
        limits_provider: LimitsProvider | None = None,
        snapshot_provider: SnapshotProvider | None = None,
        paper_exchange: PaperExchangeService | None = None,
    ) -> StrategyCliRunResult:
        raw_config = self.load_config(config_path)
        resolved_config = self.resolve_config(
            raw_config, strategy_name=strategy.__class__.__name__
        )
        start_time = events[0].ts if events else utc_now()
        end_time = events[-1].ts if events else start_time
        manifest = self._build_manifest(raw_config, resolved_config, start_time)
        self._publish_run_start(manifest, resolved_config, start_time)

        try:
            if resolved_config.mode == RunMode.REPLAY:
                artifacts = self.run_replay(
                    strategy,
                    resolved_config,
                    events=list(events),
                )
            elif resolved_config.mode == RunMode.REALTIME_PAPER:
                realtime_kwargs: dict[str, Any] = {
                    "events": list(events),
                    "constraints_provider": constraints_provider,
                    "limits_provider": limits_provider,
                    "snapshot_provider": snapshot_provider,
                    "paper_exchange": paper_exchange,
                }
                if _supports_keyword(self.run_realtime_paper, "run_id"):
                    realtime_kwargs["run_id"] = manifest.run_id
                artifacts = self.run_realtime_paper(
                    strategy,
                    resolved_config,
                    **realtime_kwargs,
                )
            else:
                artifacts = self.run_research(
                    strategy,
                    resolved_config,
                    events=list(events),
                )
        except Exception as exc:
            self._publish_run_failure(manifest.run_id, str(exc), end_time)
            raise

        metrics_summary = self.metrics_service.compute_summary(
            order_intents=artifacts["order_intents"],
            orders=artifacts["orders"],
            fills=artifacts["fills"],
            positions=artifacts["positions"],
            pnl_timeline=artifacts["pnl_timeline"],
            risk_decisions=artifacts["risk_decisions"],
            starting_equity=_as_decimal(resolved_config.risk.get("cash_available")),
        )
        final_manifest = manifest.model_copy(
            update={"end_time": end_time, "metrics_summary": metrics_summary}
        )
        self._publish_run_finish(final_manifest.run_id, metrics_summary, end_time)

        writer = RunArtifactBundleWriter(self.artifact_root)
        written_manifest = writer.write_bundle(
            final_manifest,
            signals=artifacts["signals"],
            order_intents=artifacts["order_intents"],
            orders=artifacts["orders"],
            fills=artifacts["fills"],
            positions=artifacts["positions"],
            cash_ledger=artifacts["cash_ledger"],
            pnl_timeline=artifacts["pnl_timeline"],
            risk_decisions=artifacts["risk_decisions"],
            strategy_log=artifacts["strategy_log"],
            framework_log=artifacts["framework_log"],
        )
        return StrategyCliRunResult(
            manifest=written_manifest,
            run_directory=self.artifact_root / written_manifest.run_id,
            metrics_summary=metrics_summary,
        )

    def run_replay(
        self,
        strategy: BaseStrategy,
        resolved_config: ResolvedRunConfig,
        *,
        events: list[StrategyEvent],
    ) -> dict[str, Any]:
        if not events:
            raise ValueError("replay requires events")
        runtime = self._runtime(strategy, resolved_config, events)
        result = ReplayRuntime(
            runtime,
            time_step=_parse_step_interval(resolved_config.step_interval),
        ).run(events)
        return self._artifact_payload(
            runtime=runtime,
            signals=result.signals,
            strategy_log="replay completed",
            framework_log="mode=replay",
        )

    def run_research(
        self,
        strategy: BaseStrategy,
        resolved_config: ResolvedRunConfig,
        *,
        events: list[StrategyEvent],
    ) -> dict[str, Any]:
        if not events:
            raise ValueError("research requires events")
        runtime = self._runtime(strategy, resolved_config, events)
        result = ReplayRuntime(
            runtime,
            time_step=_parse_step_interval(resolved_config.step_interval),
        ).run(events)
        return self._artifact_payload(
            runtime=runtime,
            signals=result.signals,
            strategy_log="research completed",
            framework_log="mode=research",
        )

    def run_realtime_paper(
        self,
        strategy: BaseStrategy,
        resolved_config: ResolvedRunConfig,
        *,
        events: list[StrategyEvent],
        run_id: str | None = None,
        constraints_provider: ConstraintsProvider | None = None,
        limits_provider: LimitsProvider | None = None,
        snapshot_provider: SnapshotProvider | None = None,
        paper_exchange: PaperExchangeService | None = None,
    ) -> dict[str, Any]:
        runtime = self._runtime(strategy, resolved_config, events)
        runner = RealtimeStrategyRunner(
            runtime=runtime,
            signal_execution=SignalExecutionService(
                strategy_id=str(resolved_config.strategy["name"])
            ),
            paper_exchange=paper_exchange or PaperExchangeService(),
            constraints_provider=constraints_provider
            or (lambda signal: self._constraints_from_runtime(signal, runtime)),
            limits_provider=limits_provider
            or (lambda signal: self._limits_from_runtime(signal, runtime, resolved_config)),
            snapshot_provider=snapshot_provider
            or (lambda signal: self._snapshot_from_runtime(signal, runtime)),
            runtime_registry=self.runtime_registry,
            run_id=run_id,
            strategy_name=str(resolved_config.strategy["name"]),
        )

        all_signals: list[StrategySignal] = []
        all_intents: list[Any] = []
        all_orders: list[Any] = []
        all_fills: list[Any] = []
        all_risks: list[Any] = []
        start_time = events[0].ts if events else utc_now()
        init_result = runner.on_init(start_time)
        self._collect_realtime_result(
            init_result, all_signals, all_intents, all_orders, all_fills, all_risks
        )
        for event in events:
            result = runner.on_event(event)
            self._collect_realtime_result(
                result, all_signals, all_intents, all_orders, all_fills, all_risks
            )
        all_signals.extend(runner.on_finish(events[-1].ts if events else start_time))

        return self._artifact_payload(
            runtime=runtime,
            signals=all_signals,
            order_intents=all_intents,
            orders=all_orders,
            fills=all_fills,
            risk_decisions=all_risks,
            strategy_log="realtime paper completed",
            framework_log="mode=realtime_paper",
        )

    def _artifact_payload(
        self,
        *,
        runtime: StrategyRuntime,
        signals: Sequence[Any],
        order_intents: Sequence[Any] = (),
        orders: Sequence[Any] = (),
        fills: Sequence[Any] = (),
        risk_decisions: Sequence[Any] = (),
        strategy_log: str,
        framework_log: str,
    ) -> dict[str, Any]:
        return {
            "signals": list(signals),
            "order_intents": list(order_intents),
            "orders": list(orders),
            "fills": list(fills),
            "positions": _position_rows(runtime),
            "cash_ledger": [],
            "pnl_timeline": [],
            "risk_decisions": list(risk_decisions),
            "strategy_log": strategy_log,
            "framework_log": framework_log,
        }

    def _build_manifest(
        self,
        raw_config: dict[str, Any],
        resolved_config: ResolvedRunConfig,
        start_time: datetime,
    ) -> RunManifest:
        run_id = str(raw_config.get("run_id", f"run-{uuid4().hex[:12]}"))
        universe = _mapping(raw_config.get("universe"))
        replay = _mapping(raw_config.get("replay"))
        dataset_id = str(universe.get("dataset_id", f"{run_id}-universe"))
        universe_snapshot = UniverseSnapshot(
            dataset_id=dataset_id,
            selection=universe,
            token_ids=list(universe.get("token_ids", [])),
            token_mappings=list(universe.get("token_mappings", [])),
            window_start=_parse_datetime(replay.get("start")),
            window_end=_parse_datetime(replay.get("end")),
            includes_gap_fill=bool(
                universe.get("includes_gap_fill")
                or _mapping(raw_config.get("data_sources")).get("includes_gap_fill")
            ),
        )
        return RunManifest(
            run_id=run_id,
            strategy_name=str(resolved_config.strategy["name"]),
            strategy_version=str(resolved_config.strategy["version"]),
            git_commit=self.git_commit,
            start_time=start_time,
            mode=resolved_config.mode,
            environment=str(raw_config.get("environment", "local")),
            resolved_config=resolved_config,
            universe_snapshot=universe_snapshot,
        )

    def _runtime(
        self,
        strategy: BaseStrategy,
        resolved_config: ResolvedRunConfig,
        events: Sequence[StrategyEvent],
    ) -> StrategyRuntime:
        time_window = {}
        if events:
            time_window = {"start": events[0].ts, "end": events[-1].ts}
        runtime = StrategyRuntime(strategy, resolved_config, time_window=time_window)
        runtime.update_portfolio(
            positions={},
            cash=_as_decimal(resolved_config.risk.get("cash_available")),
            open_orders=[],
        )
        return runtime

    def _publish_run_start(
        self,
        manifest: RunManifest,
        resolved_config: ResolvedRunConfig,
        start_time: datetime,
    ) -> None:
        if self.runtime_registry is None:
            return
        self.runtime_registry.set_global_mode(_global_mode_for_run(resolved_config.mode))
        self.runtime_registry.start_run(
            run_id=manifest.run_id,
            strategy_name=manifest.strategy_name,
            strategy_version=manifest.strategy_version,
            local_mode=_local_mode_for_run(resolved_config.mode),
            state=StrategyRuntimeState.STARTING,
            new_order_status=NewOrderBlockState.ALLOWED,
            heartbeat_at=start_time,
        )

    def _publish_run_finish(
        self, run_id: str, metrics_summary: dict[str, Any], end_time: datetime
    ) -> None:
        if self.runtime_registry is None:
            return
        self.runtime_registry.finish_run(
            run_id,
            at=end_time,
            latest_pnl=float(metrics_summary.get("realized_pnl", 0)),
            latest_drawdown=float(metrics_summary.get("max_drawdown", 0)),
        )

    def _publish_run_failure(
        self, run_id: str, message: str, end_time: datetime
    ) -> None:
        if self.runtime_registry is None:
            return
        self.runtime_registry.fail_run(run_id, message, at=end_time)

    def _constraints_from_runtime(
        self, signal: StrategySignal, runtime: StrategyRuntime
    ) -> MarketConstraints:
        market_data = _market_for_token(runtime, signal.token_id)
        best_bid = _as_decimal(market_data.get("best_bid")) if market_data.get("best_bid") is not None else None
        best_ask = _as_decimal(market_data.get("best_ask")) if market_data.get("best_ask") is not None else None
        spread = None
        if best_bid is not None and best_ask is not None:
            spread = best_ask - best_bid
        return MarketConstraints(
            token_id=signal.token_id,
            condition_id=_optional_str(market_data.get("condition_id")),
            tick_size=_optional_decimal(market_data.get("tick_size")) or Decimal("0.01"),
            min_order_size=_optional_decimal(market_data.get("min_order_size"))
            or Decimal("1"),
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
            active=bool(market_data.get("active", True)),
            accepting_orders=bool(market_data.get("accepting_orders", True)),
        )

    def _limits_from_runtime(
        self,
        signal: StrategySignal,
        runtime: StrategyRuntime,
        resolved_config: ResolvedRunConfig,
    ) -> RiskLimits:
        risk = resolved_config.risk
        current_position = _position_quantity(runtime, signal.token_id)
        cash_available = _as_decimal(runtime.state.portfolio.get("cash"))
        return RiskLimits(
            cash_available=cash_available,
            token_position=current_position,
            max_single_order_notional=_as_decimal(
                risk.get("max_single_order_notional", cash_available or Decimal("100"))
            ),
            max_market_position=_as_decimal(
                risk.get("max_market_position", Decimal("1000000"))
            ),
            max_token_position=_as_decimal(
                risk.get("max_token_position", Decimal("1000000"))
            ),
            current_market_position=_as_decimal(risk.get("current_market_position")),
            current_token_position=current_position,
            portfolio_exposure=_as_decimal(risk.get("portfolio_exposure")),
            event_exposure=_as_decimal(risk.get("event_exposure")),
            drawdown=_as_decimal(risk.get("drawdown")),
        )

    def _snapshot_from_runtime(
        self, signal: StrategySignal, runtime: StrategyRuntime
    ) -> BookSnapshot | None:
        market_data = _market_for_token(runtime, signal.token_id)
        best_bid = _optional_decimal(market_data.get("best_bid"))
        best_ask = _optional_decimal(market_data.get("best_ask"))
        if best_bid is None and best_ask is None:
            return None
        bids = []
        asks = []
        if best_bid is not None:
            bids.append(BookLevel(side="BUY", price=best_bid, size=Decimal("100")))
        if best_ask is not None:
            asks.append(BookLevel(side="SELL", price=best_ask, size=Decimal("100")))
        timestamp = _parse_datetime(market_data.get("event_ts")) or utc_now()
        return BookSnapshot(
            token_id=signal.token_id,
            condition_id=_optional_str(market_data.get("condition_id")),
            source_ts=timestamp,
            received_at=timestamp,
            bids=bids,
            asks=asks,
            min_order_size=_optional_decimal(market_data.get("min_order_size")),
            tick_size=_optional_decimal(market_data.get("tick_size")),
            last_trade_price=_optional_decimal(market_data.get("last_trade_price")),
        )

    def _collect_realtime_result(
        self,
        result: RealtimeExecutionResult,
        all_signals: list[Any],
        all_intents: list[Any],
        all_orders: list[Any],
        all_fills: list[Any],
        all_risks: list[Any],
    ) -> None:
        all_signals.extend(result.signals)
        all_intents.extend(result.order_intents)
        for paper_result in result.paper_results:
            if paper_result.order is not None:
                all_orders.append(paper_result.order)
            all_fills.extend(paper_result.fills)
            if paper_result.risk_decision is not None:
                all_risks.append(paper_result.risk_decision)


def _mapping(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _supports_keyword(callable_obj: Callable[..., Any], name: str) -> bool:
    signature = inspect.signature(callable_obj)
    for parameter in signature.parameters.values():
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            return True
    return name in signature.parameters


def _parse_step_interval(value: str | None) -> timedelta:
    if not value:
        return timedelta(minutes=1)
    unit = value[-1]
    amount = int(value[:-1])
    if unit == "s":
        return timedelta(seconds=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    raise ValueError(f"unsupported step interval: {value}")


def _position_rows(runtime: StrategyRuntime) -> list[dict[str, Any]]:
    positions = runtime.state.portfolio.get("positions", {})
    if not isinstance(positions, dict):
        return []
    rows: list[dict[str, Any]] = []
    for token_id, position in positions.items():
        if isinstance(position, dict):
            row = {"token_id": token_id, **position}
        else:
            row = {"token_id": token_id, "quantity": position}
        market_data = _market_for_token(runtime, token_id)
        row["mark_price"] = _optional_decimal(
            market_data.get("midpoint")
            or market_data.get("last_trade_price")
            or market_data.get("best_bid")
            or market_data.get("best_ask")
            or Decimal("0")
        )
        row["exposure"] = _as_decimal(row.get("quantity")) * _as_decimal(row["mark_price"])
        rows.append(row)
    return rows


def _market_for_token(runtime: StrategyRuntime, token_id: str) -> dict[str, Any]:
    market_data = runtime.state.market_data
    by_token = market_data.get("by_token")
    if isinstance(by_token, dict):
        token_market = by_token.get(token_id)
        if isinstance(token_market, dict):
            return token_market
    return market_data


def _position_quantity(runtime: StrategyRuntime, token_id: str) -> Decimal:
    positions = runtime.state.portfolio.get("positions", {})
    if not isinstance(positions, dict):
        return Decimal("0")
    position = positions.get(token_id)
    if isinstance(position, dict):
        return _as_decimal(position.get("quantity"))
    return _as_decimal(position)


def _as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def _optional_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return _as_decimal(value)


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def _global_mode_for_run(mode: RunMode) -> GlobalMode:
    if mode == RunMode.REALTIME_PAPER:
        return GlobalMode.PAPER
    return GlobalMode.REPLAY


def _local_mode_for_run(mode: RunMode) -> LocalRunMode:
    if mode == RunMode.RESEARCH:
        return LocalRunMode.RESEARCH
    if mode == RunMode.REALTIME_PAPER:
        return LocalRunMode.REALTIME_PAPER
    return LocalRunMode.REPLAY
