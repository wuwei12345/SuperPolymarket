"""Application services with lazy exports.

Avoid eager imports here so `python -m polymarket_quant.services.<module>`
does not pre-import sibling modules through package initialization.
"""

from __future__ import annotations

from importlib import import_module


__all__ = [
    "AutomationCliService",
    "AutomationRunner",
    "BackgroundDaemonService",
    "DashboardSnapshotService",
    "ExperimentMetricsService",
    "GapFillService",
    "MarketDataQueryService",
    "MarketDisplayService",
    "MarketRealtimeCollector",
    "OperatorQueryService",
    "OperatorRuntimeRegistry",
    "OperatorSafetyService",
    "PaperExchangeService",
    "PaperOrderResult",
    "ProductStrategyConfig",
    "RealtimeStrategyRunner",
    "RiskLevel",
    "RuntimeStateStore",
    "SignalExecutionService",
    "StrategyCliService",
    "UniverseSelector",
    "default_product_strategy_config",
    "dump_product_strategy_config",
    "load_product_strategy_config",
    "parse_product_strategy_config",
    "product_config_to_runtime_config",
    "save_product_strategy_config",
]


_EXPORTS = {
    "AutomationCliService": (
        "polymarket_quant.services.automation_cli",
        "AutomationCliService",
    ),
    "AutomationRunner": (
        "polymarket_quant.services.automation_runner",
        "AutomationRunner",
    ),
    "BackgroundDaemonService": (
        "polymarket_quant.services.background_daemon",
        "BackgroundDaemonService",
    ),
    "DashboardSnapshotService": (
        "polymarket_quant.services.dashboard_snapshot",
        "DashboardSnapshotService",
    ),
    "ExperimentMetricsService": (
        "polymarket_quant.services.experiment_metrics",
        "ExperimentMetricsService",
    ),
    "GapFillService": (
        "polymarket_quant.services.realtime_collector",
        "GapFillService",
    ),
    "MarketDataQueryService": (
        "polymarket_quant.services.market_data_queries",
        "MarketDataQueryService",
    ),
    "MarketDisplayService": (
        "polymarket_quant.services.market_display",
        "MarketDisplayService",
    ),
    "MarketRealtimeCollector": (
        "polymarket_quant.services.realtime_collector",
        "MarketRealtimeCollector",
    ),
    "OperatorQueryService": (
        "polymarket_quant.services.operator_queries",
        "OperatorQueryService",
    ),
    "OperatorRuntimeRegistry": (
        "polymarket_quant.services.operator_runtime_registry",
        "OperatorRuntimeRegistry",
    ),
    "OperatorSafetyService": (
        "polymarket_quant.services.operator_safety",
        "OperatorSafetyService",
    ),
    "PaperExchangeService": (
        "polymarket_quant.services.paper_exchange",
        "PaperExchangeService",
    ),
    "PaperOrderResult": (
        "polymarket_quant.services.paper_exchange",
        "PaperOrderResult",
    ),
    "ProductStrategyConfig": (
        "polymarket_quant.services.product_strategy_config",
        "ProductStrategyConfig",
    ),
    "RealtimeStrategyRunner": (
        "polymarket_quant.services.realtime_strategy_runner",
        "RealtimeStrategyRunner",
    ),
    "RiskLevel": (
        "polymarket_quant.services.product_strategy_config",
        "RiskLevel",
    ),
    "RuntimeStateStore": (
        "polymarket_quant.services.runtime_state_store",
        "RuntimeStateStore",
    ),
    "SignalExecutionService": (
        "polymarket_quant.services.signal_execution",
        "SignalExecutionService",
    ),
    "StrategyCliService": (
        "polymarket_quant.services.strategy_cli",
        "StrategyCliService",
    ),
    "UniverseSelector": (
        "polymarket_quant.services.universe_selector",
        "UniverseSelector",
    ),
    "default_product_strategy_config": (
        "polymarket_quant.services.product_strategy_config",
        "default_product_strategy_config",
    ),
    "dump_product_strategy_config": (
        "polymarket_quant.services.product_strategy_config",
        "dump_product_strategy_config",
    ),
    "load_product_strategy_config": (
        "polymarket_quant.services.product_strategy_config",
        "load_product_strategy_config",
    ),
    "parse_product_strategy_config": (
        "polymarket_quant.services.product_strategy_config",
        "parse_product_strategy_config",
    ),
    "product_config_to_runtime_config": (
        "polymarket_quant.services.product_strategy_config",
        "product_config_to_runtime_config",
    ),
    "save_product_strategy_config": (
        "polymarket_quant.services.product_strategy_config",
        "save_product_strategy_config",
    ),
}


def __getattr__(name: str):
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value
