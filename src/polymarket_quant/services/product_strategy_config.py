from __future__ import annotations

import json
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from polymarket_quant.domain.strategy import RunMode


DEFAULT_PRODUCT_CONFIG_PATH = Path("config/default_probe.yaml")
DEFAULT_PROBE_STRATEGY_NAME = "default_probe"
DEFAULT_PROBE_STRATEGY_VERSION = "0.1.0"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProductStrategyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductStrategySettings(ProductStrategyModel):
    name: str = DEFAULT_PROBE_STRATEGY_NAME
    risk_level: RiskLevel = RiskLevel.LOW
    stake_per_trade: Decimal = Field(default=Decimal("10"), gt=0)
    max_positions: int = Field(default=3, ge=1, le=50)

    @field_validator("name")
    @classmethod
    def name_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("strategy name cannot be blank")
        return value


class ProductUniverseSettings(ProductStrategyModel):
    min_liquidity: Decimal = Field(default=Decimal("1000"), ge=0)
    min_volume_24h: Decimal = Field(default=Decimal("250"), ge=0)
    max_days_to_expiry: int = Field(default=30, ge=1, le=365)


class ProductSimulationSettings(ProductStrategyModel):
    starting_cash: Decimal = Field(default=Decimal("1000"), gt=0)
    mode: RunMode = RunMode.REALTIME_PAPER
    environment: str = "local"

    @field_validator("environment")
    @classmethod
    def environment_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("environment cannot be blank")
        return value


class ProductStrategyConfig(ProductStrategyModel):
    strategy: ProductStrategySettings = Field(default_factory=ProductStrategySettings)
    universe: ProductUniverseSettings = Field(default_factory=ProductUniverseSettings)
    simulation: ProductSimulationSettings = Field(default_factory=ProductSimulationSettings)


def default_product_strategy_config() -> ProductStrategyConfig:
    return ProductStrategyConfig()


def load_product_strategy_config(
    path: str | Path = DEFAULT_PRODUCT_CONFIG_PATH,
) -> ProductStrategyConfig:
    config_path = Path(path)
    if not config_path.exists():
        return default_product_strategy_config()
    return parse_product_strategy_config(config_path.read_text(), suffix=config_path.suffix)


def save_product_strategy_config(
    config: ProductStrategyConfig,
    path: str | Path = DEFAULT_PRODUCT_CONFIG_PATH,
) -> None:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(dump_product_strategy_config(config))


def parse_product_strategy_config(text: str, *, suffix: str = ".yaml") -> ProductStrategyConfig:
    if suffix.lower() in {".yaml", ".yml"}:
        loaded = yaml.safe_load(text) or {}
    elif suffix.lower() == ".json":
        loaded = json.loads(text)
    else:
        raise ValueError("product strategy config must be YAML or JSON")
    if not isinstance(loaded, dict):
        raise ValueError("product strategy config must deserialize into an object")
    return ProductStrategyConfig.model_validate(loaded)


def dump_product_strategy_config(config: ProductStrategyConfig) -> str:
    return yaml.safe_dump(
        config.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=False,
    )


def product_config_to_runtime_config(
    config: ProductStrategyConfig,
    *,
    run_id: str = "default-probe",
) -> dict[str, Any]:
    strategy = config.strategy
    universe = config.universe
    simulation = config.simulation
    max_hours_to_expiry = universe.max_days_to_expiry * 24
    max_single_order_notional = _max_single_order_notional(strategy)
    max_market_position = _max_market_position(strategy)
    max_token_position = _max_token_position(strategy)
    return {
        "run_id": run_id,
        "environment": simulation.environment,
        "mode": simulation.mode.value,
        "strategy": {
            "name": strategy.name,
            "version": DEFAULT_PROBE_STRATEGY_VERSION,
            "risk_level": strategy.risk_level.value,
            "stake_per_trade": str(strategy.stake_per_trade),
            "max_positions": strategy.max_positions,
            "min_liquidity": str(universe.min_liquidity),
            "min_volume_24h": str(universe.min_volume_24h),
            "confidence": str(_confidence_for_risk(strategy.risk_level)),
        },
        "universe": {
            "dataset_id": "default-probe-market-store",
            "selection_mode": "near_expiry",
            "max_tokens": strategy.max_positions,
            "min_minutes_to_expiry": 15,
            "max_hours_to_expiry": max_hours_to_expiry,
            "candidate_limit": 100,
            "min_book_score": 3,
            "min_liquidity": str(universe.min_liquidity),
            "min_volume_24h": str(universe.min_volume_24h),
            "token_ids": [],
            "token_mappings": [],
        },
        "sizing": {"target_exposure_mode": "notional"},
        "risk": {
            "cash_available": str(simulation.starting_cash),
            "max_single_order_notional": str(max_single_order_notional),
            "max_market_position": str(max_market_position),
            "max_token_position": str(max_token_position),
            "portfolio_exposure_warning": str(strategy.stake_per_trade * strategy.max_positions),
        },
        "execution": {"time_in_force": "GTC", "post_only": False},
    }


def _max_single_order_notional(strategy: ProductStrategySettings) -> Decimal:
    multiplier = {
        RiskLevel.LOW: Decimal("1"),
        RiskLevel.MEDIUM: Decimal("1.5"),
        RiskLevel.HIGH: Decimal("2"),
    }[strategy.risk_level]
    return strategy.stake_per_trade * multiplier


def _max_market_position(strategy: ProductStrategySettings) -> Decimal:
    multiplier = {
        RiskLevel.LOW: Decimal("1"),
        RiskLevel.MEDIUM: Decimal("2"),
        RiskLevel.HIGH: Decimal("3"),
    }[strategy.risk_level]
    return strategy.stake_per_trade * multiplier


def _max_token_position(strategy: ProductStrategySettings) -> Decimal:
    return strategy.stake_per_trade * Decimal("200")


def _confidence_for_risk(risk_level: RiskLevel) -> Decimal:
    return {
        RiskLevel.LOW: Decimal("0.55"),
        RiskLevel.MEDIUM: Decimal("0.65"),
        RiskLevel.HIGH: Decimal("0.75"),
    }[risk_level]
