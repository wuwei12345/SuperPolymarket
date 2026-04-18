from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from polymarket_quant.domain.market import (
    CanonicalMarket,
    MarketSourceMap,
    SourceLabel,
)


@dataclass(frozen=True)
class SyncEvent:
    timestamp: datetime
    step: str
    source: str
    status: str
    message: str


@dataclass(frozen=True)
class MarketSyncResult:
    written_count: int
    skipped_count: int
    events: list[SyncEvent] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def normalize_markets(
    gamma_markets: Iterable[dict[str, Any]],
    clob_markets: Iterable[dict[str, Any]],
) -> tuple[list[CanonicalMarket], list[str]]:
    clob_by_condition = {
        str(condition_id): clob
        for clob in clob_markets
        if (condition_id := clob.get("condition_id"))
    }
    normalized: list[CanonicalMarket] = []
    skipped: list[str] = []

    for gamma in gamma_markets:
        condition_id = _first_present(gamma, "conditionId", "condition_id")
        if not condition_id:
            skipped.append("Gamma market missing condition_id")
            continue

        clob = clob_by_condition.get(str(condition_id))
        if not clob:
            skipped.append(f"{condition_id}: missing CLOB simplified market")
            continue

        active = bool(gamma.get("active", True)) and bool(clob.get("active", True))
        closed = bool(gamma.get("closed", False)) or bool(clob.get("closed", False))
        archived = bool(clob.get("archived", False))
        accepting_orders = bool(
            clob.get(
                "accepting_orders",
                gamma.get("acceptingOrders", gamma.get("accepting_orders", False)),
            )
        )

        yes_token_id, no_token_id = _extract_yes_no_tokens(clob, gamma)
        try:
            market = CanonicalMarket(
                market_id=_optional_string(_first_present(gamma, "id", "marketId")),
                question=str(gamma.get("question") or clob.get("question") or ""),
                category=_optional_string(
                    _first_present(gamma, "category", "eventCategory", "groupItemTitle")
                ),
                liquidity=_optional_float(
                    _first_present(gamma, "liquidity", "liquidityNum")
                ),
                end_date=_first_present(gamma, "endDate", "end_date", "end_date_iso"),
                condition_id=str(condition_id),
                yes_token_id=yes_token_id or "",
                no_token_id=no_token_id or "",
                active=active and not closed and not archived,
                accepting_orders=accepting_orders,
                restricted=_optional_bool(
                    _first_present(gamma, "restricted", "isRestricted")
                ),
                source_map=MarketSourceMap(
                    question=SourceLabel.GAMMA,
                    category=SourceLabel.GAMMA,
                    liquidity=SourceLabel.GAMMA,
                    end_date=SourceLabel.GAMMA,
                    condition_id=SourceLabel.NORMALIZED,
                    yes_token_id=SourceLabel.CLOB,
                    no_token_id=SourceLabel.CLOB,
                ),
                raw_gamma=gamma,
                raw_clob=clob,
            )
        except ValueError as error:
            skipped.append(f"{condition_id}: invalid canonical market ({error})")
            continue

        if not market.is_phase1_valid():
            skipped.append(f"{condition_id}: not active + accepting orders with IDs")
            continue
        normalized.append(market)

    return normalized, skipped


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _first_present(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def _optional_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _extract_yes_no_tokens(
    clob: dict[str, Any], gamma: dict[str, Any]
) -> tuple[str | None, str | None]:
    clob_tokens = clob.get("tokens") or []
    yes_token = _token_for_outcome(clob_tokens, "yes")
    no_token = _token_for_outcome(clob_tokens, "no")
    if yes_token and no_token:
        return yes_token, no_token

    parsed_gamma_tokens = _parse_clob_token_ids(gamma.get("clobTokenIds"))
    if len(parsed_gamma_tokens) >= 2:
        return yes_token or parsed_gamma_tokens[0], no_token or parsed_gamma_tokens[1]

    positional_clob_tokens = [_token_id(token) for token in clob_tokens]
    positional_clob_tokens = [token for token in positional_clob_tokens if token]
    if len(positional_clob_tokens) >= 2:
        return yes_token or positional_clob_tokens[0], no_token or positional_clob_tokens[1]

    return yes_token, no_token


def _token_for_outcome(tokens: Iterable[dict[str, Any]], outcome: str) -> str | None:
    for token in tokens:
        token_outcome = str(token.get("outcome") or token.get("name") or "").lower()
        if token_outcome == outcome:
            return _token_id(token)
    return None


def _token_id(token: dict[str, Any]) -> str | None:
    value = _first_present(token, "token_id", "tokenId", "id", "asset_id")
    return None if value is None else str(value)


def _parse_clob_token_ids(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
    else:
        parsed = value
    if not isinstance(parsed, list):
        return []
    return [str(token_id) for token_id in parsed if token_id]
