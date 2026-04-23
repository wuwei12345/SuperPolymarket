"""Application services with lazy exports.

Avoid eager imports here so `python -m polymarket_quant.services.<module>`
does not pre-import sibling modules through package initialization.
"""

from __future__ import annotations

from importlib import import_module


__all__ = [
    "AutomationCliService",
    "AutomationRunner",
    "ExperimentMetricsService",
    "GapFillService",
    "MarketDataQueryService",
    "MarketRealtimeCollector",
    "OperatorQueryService",
    "OperatorRuntimeRegistry",
    "OperatorSafetyService",
    "PaperExchangeService",
    "PaperOrderResult",
    "RealtimeStrategyRunner",
    "SignalExecutionService",
    "StrategyCliService",
    "UniverseSelector",
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
    "RealtimeStrategyRunner": (
        "polymarket_quant.services.realtime_strategy_runner",
        "RealtimeStrategyRunner",
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
