# Nordmarkt

A bilingual (Swedish / English) commerce platform. Python + FastAPI on the
back, Next.js 15 on the front, PostgreSQL and Redis underneath.

This is not a CRUD demo. The interesting parts are the four problems that make
commerce backends hard, and the specific choices made about each:

| Problem | Where it is solved | Approach |
|---|---|---|
| Two shoppers, one last unit | `modules/inventory/service.py` | Conditional `UPDATE` under the row lock; no distributed lock, no retry loop |
| Double-charging on retry | `core/idempotency.py`, `api/routers/checkout.py` | Redis `SET NX` claim plus cached response |
| State change and side effect drifting apart | `shared/outbox.py`, `workers/outbox_relay.py` | Transactional outbox, drained with `SKIP LOCKED` |
| Money that does not round correctly | `core/money.py` | Integer minor units, half-up rounding, no floats anywhere |

## Running it

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

- Storefront: http://localhost:3000/sv (and `/en`)
- API docs: http://localhost:8000/docs
- Demo account: `demo@nordmarkt.se` / `nordmarkt-demo-2026`

The API container runs migrations and seeds a 24-product bilingual catalogue on
first boot.

## Repository layout

```
backend/
  app/
    core/         config, money, errors, security, pagination, idempotency
    db/           declarative base, session factory, Alembic migrations
    shared/       Unit of Work, domain events, outbox, localisation
    modules/      catalog · identity · cart · inventory · orders · payments
    api/          routers, dependencies, middleware — the only HTTP-aware layer
    workers/      outbox relay, reservation sweeper
  tests/          unit (pure domain) + integration (real Postgres)
frontend/
  src/app/[locale]/   App Router pages, locale-prefixed
  src/components/     server components by default, client only where needed
  src/lib/            typed API client
  messages/           sv.json · en.json (key parity enforced)
```

## Testing

```bash
cd backend
pip install -e ".[dev]"
pytest tests/unit           # no infrastructure required
docker compose up -d db
pytest -m integration       # includes the concurrent-checkout race test
```

`tests/integration/test_checkout_concurrency.py` fires eight simultaneous
reservations at a variant with one unit in stock and asserts that exactly one
succeeds. It is written against a real database on purpose: the property under
test belongs to Postgres, not to Python, so a mocked session would prove
nothing.

Coverage is 28% and concentrated on the domain core (money, order state
machine, localisation, pagination) rather than spread thin across HTTP glue.
Service-layer tests are the next increment.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — layering, request lifecycle, module boundaries
- [`docs/decisions.md`](docs/decisions.md) — the trade-offs, including what was deliberately *not* built

## Notes on scope

Product photography is proxied from LoremFlickr so the repository carries no
binary assets. The payment gateway is a deterministic sandbox behind a
`PaymentGateway` protocol; swapping in Klarna or Swish is a new adapter, not a
change to checkout. Neither of those is production infrastructure, and both are
isolated behind an interface for exactly that reason.
