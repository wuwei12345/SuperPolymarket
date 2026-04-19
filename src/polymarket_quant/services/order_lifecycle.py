from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from polymarket_quant.domain.market_data import utc_now
from polymarket_quant.domain.simulation import (
    OrderIntent,
    OrderStateTransition,
    OrderStatus,
    SimulatedOrder,
)


LEGAL_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.ACCEPTED, OrderStatus.REJECTED},
    OrderStatus.ACCEPTED: {OrderStatus.OPEN, OrderStatus.REJECTED},
    OrderStatus.OPEN: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCEL_REQUESTED,
        OrderStatus.REPLACE_REQUESTED,
        OrderStatus.EXPIRED,
    },
    OrderStatus.PARTIALLY_FILLED: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCEL_REQUESTED,
        OrderStatus.REPLACE_REQUESTED,
        OrderStatus.EXPIRED,
    },
    OrderStatus.CANCEL_REQUESTED: {OrderStatus.CANCELED, OrderStatus.FILLED},
    OrderStatus.REPLACE_REQUESTED: {OrderStatus.REPLACED, OrderStatus.CANCELED},
    OrderStatus.FILLED: set(),
    OrderStatus.CANCELED: set(),
    OrderStatus.REPLACED: set(),
    OrderStatus.REJECTED: set(),
    OrderStatus.EXPIRED: set(),
}


class OrderLifecycleService:
    def create_order(
        self, intent: OrderIntent, now: datetime | None = None
    ) -> SimulatedOrder:
        timestamp = now or utc_now()
        return SimulatedOrder(
            **intent.model_dump(),
            remaining_size=intent.size,
            status=OrderStatus.PENDING,
            updated_at=timestamp,
        )

    def transition(
        self,
        order: SimulatedOrder,
        new_status: OrderStatus,
        reason: str,
        now: datetime | None = None,
    ) -> tuple[SimulatedOrder, OrderStateTransition]:
        if new_status not in LEGAL_TRANSITIONS.get(order.status, set()):
            raise ValueError(
                f"invalid order transition: {order.status} -> {new_status}"
            )
        timestamp = now or utc_now()
        accepted_at = order.accepted_at
        if new_status == OrderStatus.ACCEPTED and accepted_at is None:
            accepted_at = timestamp
        updated = order.model_copy(
            update={
                "status": new_status,
                "updated_at": timestamp,
                "accepted_at": accepted_at,
                "reject_reason": reason if new_status == OrderStatus.REJECTED else None,
            }
        )
        transition = OrderStateTransition(
            client_order_id=order.client_order_id,
            from_status=order.status,
            to_status=new_status,
            reason=reason,
            created_at=timestamp,
        )
        return updated, transition

    def request_cancel(
        self, order: SimulatedOrder, now: datetime | None = None
    ) -> tuple[SimulatedOrder, OrderStateTransition]:
        return self.transition(order, OrderStatus.CANCEL_REQUESTED, "cancel_requested", now)

    def cancel(
        self, order: SimulatedOrder, now: datetime | None = None
    ) -> tuple[SimulatedOrder, OrderStateTransition]:
        return self.transition(order, OrderStatus.CANCELED, "canceled", now)

    def request_replace(
        self, order: SimulatedOrder, now: datetime | None = None
    ) -> tuple[SimulatedOrder, OrderStateTransition]:
        return self.transition(
            order, OrderStatus.REPLACE_REQUESTED, "replace_requested", now
        )

    def reject(
        self, order: SimulatedOrder, reason: str, now: datetime | None = None
    ) -> tuple[SimulatedOrder, OrderStateTransition]:
        return self.transition(order, OrderStatus.REJECTED, reason, now)

    def mark_open(
        self, order: SimulatedOrder, now: datetime | None = None
    ) -> tuple[SimulatedOrder, OrderStateTransition]:
        return self.transition(order, OrderStatus.OPEN, "opened", now)

    def mark_partially_filled(
        self,
        order: SimulatedOrder,
        remaining_size: Decimal,
        now: datetime | None = None,
    ) -> tuple[SimulatedOrder, OrderStateTransition]:
        if remaining_size <= 0:
            raise ValueError("remaining_size must be positive for partial fill")
        updated = order.model_copy(update={"remaining_size": remaining_size})
        return self.transition(
            updated, OrderStatus.PARTIALLY_FILLED, "partially_filled", now
        )

    def mark_filled(
        self, order: SimulatedOrder, now: datetime | None = None
    ) -> tuple[SimulatedOrder, OrderStateTransition]:
        updated = order.model_copy(update={"remaining_size": Decimal("0")})
        return self.transition(updated, OrderStatus.FILLED, "filled", now)
