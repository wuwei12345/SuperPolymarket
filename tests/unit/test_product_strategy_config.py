from __future__ import annotations

from decimal import Decimal

from polymarket_quant.domain.strategy import RunMode
from polymarket_quant.services.product_strategy_config import (
    RiskLevel,
    default_product_strategy_config,
    dump_product_strategy_config,
    parse_product_strategy_config,
    product_config_to_runtime_config,
)


def test_product_strategy_config_round_trips_yaml() -> None:
    config = default_product_strategy_config()
    dumped = dump_product_strategy_config(config)
    parsed = parse_product_strategy_config(dumped)

    assert parsed.strategy.name == "default_probe"
    assert parsed.strategy.risk_level == RiskLevel.LOW
    assert parsed.strategy.stake_per_trade == Decimal("10")
    assert parsed.strategy.max_positions == 3
    assert parsed.simulation.mode == RunMode.REALTIME_PAPER


def test_product_strategy_config_maps_simple_controls_to_runtime_yaml() -> None:
    config = parse_product_strategy_config(
        """
strategy:
  name: default_probe
  risk_level: medium
  stake_per_trade: '25'
  max_positions: 4
universe:
  min_liquidity: '1500'
  min_volume_24h: '500'
  max_days_to_expiry: 21
simulation:
  starting_cash: '2000'
  mode: realtime_paper
  environment: local
"""
    )

    runtime = product_config_to_runtime_config(config, run_id="probe-test")

    assert runtime["run_id"] == "probe-test"
    assert runtime["strategy"]["name"] == "default_probe"
    assert runtime["strategy"]["risk_level"] == "medium"
    assert runtime["strategy"]["stake_per_trade"] == "25"
    assert runtime["universe"]["max_tokens"] == 4
    assert runtime["universe"]["max_hours_to_expiry"] == 504
    assert runtime["sizing"]["target_exposure_mode"] == "notional"
    assert runtime["risk"]["cash_available"] == "2000"
    assert runtime["risk"]["max_single_order_notional"] == "37.5"
