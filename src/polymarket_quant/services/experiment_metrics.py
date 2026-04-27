from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class ExperimentMetricsService:
    def compute_summary(
        self,
        *,
        order_intents: Sequence[Mapping[str, Any] | BaseModel] = (),
        orders: Sequence[Mapping[str, Any] | BaseModel] = (),
        fills: Sequence[Mapping[str, Any] | BaseModel] = (),
        positions: Sequence[Mapping[str, Any] | BaseModel] = (),
        pnl_timeline: Sequence[Mapping[str, Any] | BaseModel] = (),
        risk_decisions: Sequence[Mapping[str, Any] | BaseModel] = (),
        starting_equity: Decimal | int | float | str | None = None,
    ) -> dict[str, Any]:
        intent_rows = [_row_to_dict(row) for row in order_intents]
        order_rows = [_row_to_dict(row) for row in orders]
        fill_rows = sorted(
            (_row_to_dict(row) for row in fills),
            key=lambda row: _parse_timestamp(row.get("created_at"))
            or _parse_timestamp(row.get("source_ts"))
            or datetime.min,
        )
        position_rows = [_row_to_dict(row) for row in positions]
        pnl_rows = [_row_to_dict(row) for row in pnl_timeline]
        risk_rows = [_row_to_dict(row) for row in risk_decisions]

        derived_pnl_rows = (
            pnl_rows
            if pnl_rows
            else self.derive_pnl_timeline_from_fills(fill_rows, position_rows)
        )
        realized_pnl, unrealized_pnl, total_pnl = self._pnl_totals(derived_pnl_rows)
        starting = _as_decimal(starting_equity)
        turnover = sum(
            _as_decimal(fill.get("price")) * _as_decimal(fill.get("size"))
            for fill in fill_rows
        )
        intended_notional = sum(
            _as_decimal(intent.get("price")) * _as_decimal(intent.get("size"))
            for intent in intent_rows
        )
        fill_rate = _safe_divide(turnover, intended_notional)
        cancel_rate = _safe_divide(
            Decimal(
                sum(
                    1
                    for order in order_rows
                    if str(order.get("status", "")).endswith("CANCELED")
                )
            ),
            Decimal(len(order_rows)),
        )
        average_holding_time = self._average_holding_time_seconds(fill_rows)
        max_drawdown = self._max_drawdown(derived_pnl_rows)
        exposure_peak = self._exposure_peak(position_rows)
        reject_count = int(
            sum(
                1
                for decision in risk_rows
                if str(decision.get("decision")) == "REJECT"
            )
        )
        slippage = self._slippage_metrics(intent_rows, fill_rows)

        return {
            "total_return": _safe_divide(total_pnl, starting),
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "turnover": turnover,
            "fill_rate": fill_rate,
            "cancel_rate": cancel_rate,
            "average_holding_time_seconds": average_holding_time,
            "max_drawdown": max_drawdown,
            "exposure_peak": exposure_peak,
            "reject_count": reject_count,
            "slippage_notional": slippage["notional"],
            "slippage_average": slippage["average"],
            "slippage_bps": slippage["bps"],
        }

    def derive_pnl_timeline_from_fills(
        self,
        fills: Sequence[Mapping[str, Any] | BaseModel],
        positions: Sequence[Mapping[str, Any] | BaseModel] = (),
    ) -> list[dict[str, Any]]:
        fill_rows = sorted(
            (_row_to_dict(row) for row in fills),
            key=lambda row: _parse_timestamp(row.get("created_at"))
            or _parse_timestamp(row.get("source_ts"))
            or datetime.min,
        )
        if not fill_rows:
            return []

        open_lots: dict[str, deque[tuple[Decimal, Decimal]]] = defaultdict(deque)
        last_price_by_token: dict[str, Decimal] = {}
        realized_pnl = Decimal("0")
        rows: list[dict[str, Any]] = []

        for fill in fill_rows:
            token_id = str(fill.get("token_id"))
            side = str(fill.get("side"))
            price = _as_decimal(fill.get("price"))
            size = _as_decimal(fill.get("size"))
            timestamp = _parse_timestamp(fill.get("created_at")) or _parse_timestamp(
                fill.get("source_ts")
            )
            if not token_id or size <= 0:
                continue
            last_price_by_token[token_id] = price
            if side == "BUY":
                open_lots[token_id].append((size, price))
            elif side == "SELL":
                remaining = size
                lots = open_lots[token_id]
                while lots and remaining > 0:
                    lot_size, lot_price = lots[0]
                    matched = min(lot_size, remaining)
                    realized_pnl += matched * (price - lot_price)
                    remaining -= matched
                    if matched == lot_size:
                        lots.popleft()
                    else:
                        lots[0] = (lot_size - matched, lot_price)

            unrealized_pnl, exposure = self._open_lot_unrealized_and_exposure(
                open_lots,
                last_price_by_token,
                positions,
            )
            rows.append(
                {
                    "ts": timestamp,
                    "realized_pnl": realized_pnl,
                    "unrealized_pnl": unrealized_pnl,
                    "total_pnl": realized_pnl + unrealized_pnl,
                    "exposure": exposure,
                }
            )
        return rows

    def _open_lot_unrealized_and_exposure(
        self,
        open_lots: dict[str, deque[tuple[Decimal, Decimal]]],
        last_price_by_token: dict[str, Decimal],
        positions: Sequence[Mapping[str, Any] | BaseModel],
    ) -> tuple[Decimal, Decimal]:
        mark_by_token = {
            str(row.get("token_id")): _as_decimal(
                row.get("mark_price") or row.get("current_price")
            )
            for row in (_row_to_dict(position) for position in positions)
            if row.get("token_id")
        }
        unrealized_pnl = Decimal("0")
        exposure = Decimal("0")
        for token_id, lots in open_lots.items():
            mark_price = mark_by_token.get(token_id, last_price_by_token.get(token_id, Decimal("0")))
            for lot_size, lot_price in lots:
                unrealized_pnl += lot_size * (mark_price - lot_price)
                exposure += abs(lot_size * mark_price)
        return unrealized_pnl, exposure

    def _pnl_totals(self, pnl_rows: Sequence[dict[str, Any]]) -> tuple[Decimal, Decimal, Decimal]:
        if not pnl_rows:
            return Decimal("0"), Decimal("0"), Decimal("0")
        last_row = pnl_rows[-1]
        realized = _as_decimal(last_row.get("realized_pnl"))
        unrealized = _as_decimal(last_row.get("unrealized_pnl"))
        total = _as_decimal(last_row.get("total_pnl"))
        return realized, unrealized, total

    def _average_holding_time_seconds(self, fills: Sequence[dict[str, Any]]) -> Decimal:
        open_lots: dict[str, deque[tuple[Decimal, datetime]]] = defaultdict(deque)
        total_seconds = Decimal("0")
        closed_size = Decimal("0")

        for fill in fills:
            side = str(fill.get("side"))
            size = _as_decimal(fill.get("size"))
            timestamp = _parse_timestamp(fill.get("created_at")) or _parse_timestamp(
                fill.get("source_ts")
            )
            if timestamp is None or size <= 0:
                continue
            token_id = str(fill.get("token_id"))
            lots = open_lots[token_id]
            if side == "BUY":
                lots.append((size, timestamp))
                continue

            remaining = size
            while lots and remaining > 0:
                lot_size, lot_timestamp = lots[0]
                matched = min(lot_size, remaining)
                total_seconds += Decimal(str((timestamp - lot_timestamp).total_seconds())) * matched
                closed_size += matched
                remaining -= matched
                if matched == lot_size:
                    lots.popleft()
                else:
                    lots[0] = (lot_size - matched, lot_timestamp)

        return _safe_divide(total_seconds, closed_size)

    def _max_drawdown(self, pnl_rows: Sequence[dict[str, Any]]) -> Decimal:
        peak = Decimal("0")
        max_drawdown = Decimal("0")
        for row in pnl_rows:
            total = _as_decimal(row.get("total_pnl"))
            if total > peak:
                peak = total
            drawdown = peak - total
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        return max_drawdown

    def _exposure_peak(self, positions: Sequence[dict[str, Any]]) -> Decimal:
        peak = Decimal("0")
        for row in positions:
            if "exposure" in row:
                exposure = abs(_as_decimal(row.get("exposure")))
            else:
                exposure = abs(_as_decimal(row.get("quantity"))) * _as_decimal(
                    row.get("mark_price", 1)
                )
            if exposure > peak:
                peak = exposure
        return peak

    def _slippage_metrics(
        self, order_intents: Sequence[dict[str, Any]], fills: Sequence[dict[str, Any]]
    ) -> dict[str, Decimal]:
        intents_by_id = {
            str(intent.get("client_order_id")): intent for intent in order_intents
        }
        total_slippage = Decimal("0")
        total_units = Decimal("0")
        total_notional = Decimal("0")

        for fill in fills:
            intent = intents_by_id.get(str(fill.get("client_order_id")))
            if intent is None:
                continue
            expected_price = _as_decimal(intent.get("price"))
            fill_price = _as_decimal(fill.get("price"))
            size = _as_decimal(fill.get("size"))
            side = str(fill.get("side"))
            per_unit_slippage = (
                fill_price - expected_price if side == "BUY" else expected_price - fill_price
            )
            total_slippage += per_unit_slippage * size
            total_units += size
            total_notional += expected_price * size

        average = _safe_divide(total_slippage, total_units)
        bps = _safe_divide(total_slippage, total_notional) * Decimal("10000")
        return {"notional": total_slippage, "average": average, "bps": bps}


def _row_to_dict(row: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    if isinstance(row, BaseModel):
        return row.model_dump(mode="python")
    return dict(row)


def _as_decimal(value: Decimal | int | float | str | None) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("0")
    return numerator / denominator


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None
