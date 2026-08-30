"""Payment provider abstraction.

The gateway is behind a protocol so the domain never imports a vendor SDK.
Swapping Swish for Klarna is a new adapter, not a change to checkout. The
sandbox adapter below is deterministic, which makes the payment paths testable
without network access.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, PaymentDeclinedError
from app.modules.orders.models import Order
from app.modules.payments.models import Payment, PaymentStatus, ProcessedWebhook
from app.shared.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True)
class ChargeIntent:
    reference: str
    redirect_url: str
    status: PaymentStatus


class PaymentGateway(Protocol):
    name: str

    async def create_intent(
        self, *, amount_minor_units: int, currency: str, order_number: str
    ) -> ChargeIntent: ...

    async def capture(self, reference: str) -> bool: ...


class SandboxGateway:
    """Deterministic stand-in for a real PSP.

    Order numbers ending in ``9`` are declined so the failure path can be
    exercised in demos and integration tests without special-casing the code
    under test.
    """

    name = "swish_sandbox"

    async def create_intent(
        self, *, amount_minor_units: int, currency: str, order_number: str
    ) -> ChargeIntent:
        reference = f"sbx_{secrets.token_hex(12)}"
        declined = order_number.endswith("9")
        return ChargeIntent(
            reference=reference,
            redirect_url=f"https://sandbox.nordmarkt.test/pay/{reference}",
            status=PaymentStatus.FAILED if declined else PaymentStatus.AUTHORIZED,
        )

    async def capture(self, reference: str) -> bool:
        return reference.startswith("sbx_")


class PaymentService:
    def __init__(self, uow: UnitOfWork, gateway: PaymentGateway) -> None:
        self._uow = uow
        self._gateway = gateway

    @property
    def _session(self) -> AsyncSession:
        return self._uow.session

    async def start(self, order: Order) -> Payment:
        intent = await self._gateway.create_intent(
            amount_minor_units=order.total_minor_units,
            currency=order.currency,
            order_number=order.order_number,
        )
        payment = Payment(
            order_id=order.id,
            provider=self._gateway.name,
            provider_reference=intent.reference,
            status=intent.status,
            amount_minor_units=order.total_minor_units,
            currency=order.currency,
            raw_response={"redirect_url": intent.redirect_url},
        )
        self._session.add(payment)
        await self._session.flush()

        if intent.status is PaymentStatus.FAILED:
            payment.failure_reason = "declined_by_issuer"
            raise PaymentDeclinedError("payment was declined", reference=intent.reference)
        return payment

    async def capture(self, reference: str) -> Payment:
        payment = await self._session.scalar(
            select(Payment).where(Payment.provider_reference == reference)
        )
        if payment is None:
            raise NotFoundError("payment not found")
        if payment.status is PaymentStatus.CAPTURED:
            return payment  # idempotent: a repeat capture is a no-op
        if payment.status is not PaymentStatus.AUTHORIZED:
            raise ConflictError("payment is not in a capturable state", status=payment.status.value)

        if not await self._gateway.capture(reference):
            payment.status = PaymentStatus.FAILED
            payment.failure_reason = "capture_rejected"
            raise PaymentDeclinedError("capture rejected")

        payment.status = PaymentStatus.CAPTURED
        payment.captured_at = datetime.now(UTC)
        return payment

    async def record_webhook(self, provider: str, event_id: str, payload: dict) -> bool:
        """Returns False if this callback was already handled."""
        self._session.add(ProcessedWebhook(provider=provider, event_id=event_id, payload=payload))
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return False
        return True


def verify_signature(secret: str, body: bytes, signature: str) -> bool:
    """Constant-time HMAC check on provider callbacks."""
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _unused(_: uuid.UUID) -> None:  # pragma: no cover
    return None
