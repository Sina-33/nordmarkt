"""Error taxonomy.

The domain layer raises these. The API layer is the only place that knows
about HTTP, so each error carries a stable machine-readable ``code`` that the
frontend switches on, plus a translation key so the client renders the message
in the shopper's own language rather than the server's.
"""

from typing import Any


class DomainError(Exception):
    code = "domain_error"
    status_code = 400
    message_key = "errors.generic"

    def __init__(self, message: str | None = None, **context: Any) -> None:
        self.context = context
        super().__init__(message or self.code)


class NotFoundError(DomainError):
    code = "not_found"
    status_code = 404
    message_key = "errors.not_found"


class ConflictError(DomainError):
    code = "conflict"
    status_code = 409
    message_key = "errors.conflict"


class ValidationFailedError(DomainError):
    code = "validation_failed"
    status_code = 422
    message_key = "errors.validation"


class UnauthorizedError(DomainError):
    code = "unauthorized"
    status_code = 401
    message_key = "errors.unauthorized"


class ForbiddenError(DomainError):
    code = "forbidden"
    status_code = 403
    message_key = "errors.forbidden"


class InsufficientStockError(ConflictError):
    code = "insufficient_stock"
    message_key = "errors.insufficient_stock"


class CartEmptyError(ValidationFailedError):
    code = "cart_empty"
    message_key = "errors.cart_empty"


class PriceChangedError(ConflictError):
    code = "price_changed"
    message_key = "errors.price_changed"


class PaymentDeclinedError(ConflictError):
    code = "payment_declined"
    message_key = "errors.payment_declined"


class IdempotencyConflictError(ConflictError):
    code = "idempotency_conflict"
    message_key = "errors.idempotency_conflict"
