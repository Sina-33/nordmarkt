import pytest

from app.core.errors import ConflictError
from app.modules.orders.models import Order, OrderStatus


def make_order(status: OrderStatus) -> Order:
    order = Order(
        order_number="NM-260830-ABC123",
        subtotal_minor_units=0,
        vat_minor_units=0,
        total_minor_units=0,
        shipping_address={},
        billing_address={},
    )
    order.status = status
    return order


def test_happy_path_transitions() -> None:
    order = make_order(OrderStatus.PENDING_PAYMENT)
    for target in (
        OrderStatus.PAID,
        OrderStatus.PACKING,
        OrderStatus.SHIPPED,
        OrderStatus.DELIVERED,
    ):
        order.transition_to(target)
    assert order.status is OrderStatus.DELIVERED


def test_cancelled_order_is_terminal() -> None:
    order = make_order(OrderStatus.CANCELLED)
    with pytest.raises(ConflictError):
        order.transition_to(OrderStatus.SHIPPED)


def test_cannot_ship_before_payment() -> None:
    order = make_order(OrderStatus.PENDING_PAYMENT)
    with pytest.raises(ConflictError):
        order.transition_to(OrderStatus.SHIPPED)


def test_delivered_can_still_be_refunded() -> None:
    order = make_order(OrderStatus.DELIVERED)
    order.transition_to(OrderStatus.REFUNDED)
    assert order.status is OrderStatus.REFUNDED
