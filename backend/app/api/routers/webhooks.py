from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import select

from app.api.deps import CheckoutDep, PaymentsDep, UoWDep
from app.core.logging import get_logger
from app.modules.orders.models import Order

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger(__name__)


@router.post("/payments/{provider}", status_code=status.HTTP_202_ACCEPTED)
async def payment_callback(
    provider: str,
    request: Request,
    uow: UoWDep,
    payments: PaymentsDep,
    checkout: CheckoutDep,
) -> Response:
    """Handle a provider callback.

    Two properties matter more than anything else here:

    * **Idempotency.** Providers retry, so the same event id must never be
      applied twice. ``record_webhook`` inserts under a unique constraint and
      short-circuits on conflict.
    * **Fast acknowledgement.** Anything slow belongs in the outbox relay, not
      in this handler, or the provider times out and retries a job that was
      actually fine.
    """
    body = await request.json()
    event_id = str(body.get("event_id", ""))
    if not event_id:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    if not await payments.record_webhook(provider, event_id, body):
        logger.info("webhook_duplicate_ignored", provider=provider, event_id=event_id)
        return Response(status_code=status.HTTP_202_ACCEPTED)

    reference = body.get("reference")
    if body.get("type") == "payment.captured" and reference:
        payment = await payments.capture(reference)
        order = await uow.session.scalar(select(Order).where(Order.id == payment.order_id))
        if order is not None:
            await checkout.mark_paid(order, reference)

    await uow.commit()
    return Response(status_code=status.HTTP_202_ACCEPTED)
