# Decision log

Each entry states the decision, the alternatives considered, and what it costs.
The costs are the honest ones — several of these are trades I would revisit at
a different scale.

---

## 1. Modular monolith over microservices

**Chose:** one deployable, six modules with enforced import boundaries.

**Rejected:** service-per-domain.

**Why:** checkout touches cart, inventory, orders and payments in one atomic
step. As services, that is a saga with compensating transactions — a large
amount of machinery to buy independent scaling that a single Postgres instance
does not yet need.

**Cost:** everything scales together, and one module's memory leak takes down
the rest. Mitigated by drawing module boundaries where service boundaries would
go: `InventoryService` already talks to nothing but its own tables, so
extracting it later is mechanical.

---

## 2. Conditional UPDATE over pessimistic locking or Redis locks

**Chose:** `UPDATE ... WHERE on_hand - reserved >= :qty`, checked via
`rowcount`.

**Rejected:**
- `SELECT ... FOR UPDATE` then write — correct, but holds the lock across a
  Python round trip and serialises every add-to-cart on a popular item.
- A Redis distributed lock — introduces a second source of truth that can fail
  open during a failover, at which point the database happily oversells.

**Why:** the predicate is evaluated inside the same row lock Postgres takes for
the write. No lock is held across application code, and the database remains
the single authority.

**Cost:** the logic lives in SQL rather than in a readable Python method, which
is harder for a newcomer to find. Addressed with a comment block at the top of
the service explaining exactly why.

---

## 3. Transactional outbox over direct publishing

**Chose:** events written as rows in the same transaction, drained by a
separate relay process.

**Rejected:** publishing to a broker inside the request handler.

**Why:** direct publishing is a distributed transaction in disguise. Either the
order commits and the publish fails (no confirmation email, silently), or the
publish succeeds and the transaction rolls back (a confirmation for an order
that does not exist). The outbox removes the failure mode entirely.

**Cost:** added latency between the state change and the side effect, bounded
by the relay poll interval — currently up to one second. Acceptable for email
and warehouse notification; it would not be for anything a shopper is watching.

---

## 4. Integer minor units over Decimal or float

**Chose:** every amount is an integer count of öre, wrapped in a `Money` value
object.

**Rejected:**
- `float` — `0.1 + 0.2` drift shows up in an accounting reconciliation three
  months later, not in a test.
- `Decimal` throughout — correct, but nothing stops a caller passing an
  unquantised value, and the currency travels separately from the amount.

**Why:** `Money` refuses to add SEK to EUR, refuses multiplication by a float,
and rounds half-up (not banker's rounding, which disagrees with how a Swedish
invoice is expected to round).

**Cost:** conversion at every boundary. `MoneyOut` handles it in one place.

---

## 5. JSONB translations over a translations table

**Chose:** `title` and `description` are JSONB maps of locale to string.

**Rejected:** `product_translations(product_id, locale, field, value)`.

**Why:** a product page becomes one row fetch instead of a join per language,
and adding a third locale is a data change rather than a schema change.

**Cost:** no referential integrity on locale keys, and no easy way to query
"products missing an English description" without a JSONB scan. At two locales
this is comfortably the right side of the trade; at fifteen it would not be.

---

## 6. Keyset pagination over offset

**Chose:** opaque base64 cursors encoding the `ORDER BY` tuple.

**Rejected:** `LIMIT/OFFSET`.

**Why:** offset must count and discard every skipped row, so page 500 is
hundreds of times more expensive than page 1. Worse, when the underlying list
changes between requests, offset shows some items twice and skips others.

**Cost:** no jump-to-page-N. For an infinite-scroll storefront that is a feature
nobody asked for; for an admin table it would be a real loss, and that surface
would need a different approach.

---

## 7. Refresh-token rotation with reuse detection

**Chose:** short-lived access tokens (15 min) plus rotating refresh tokens,
stored hashed, with a server-side session row.

**Rejected:** long-lived JWTs with no server state.

**Why:** stateless JWTs cannot be revoked, so "sign out of all devices" becomes
a lie and a leaked token stays valid until expiry. Storing only a hash means a
database dump does not hand an attacker working credentials. Presenting a
retired token revokes the whole family, on the assumption it was stolen.

**Cost:** a database read on every refresh, and session rows to prune. Both are
cheap relative to the failure they prevent.

---

## 8. Server-side money formatting

**Chose:** the API returns a preformatted, locale-correct string alongside the
raw minor units.

**Rejected:** `Intl.NumberFormat` on the client.

**Why:** the same amount rendered by two code paths eventually disagrees, and
the one the shopper sees must be the one they are charged. Sending both means
the client can still sort or compare on `minor_units`.

**Cost:** slightly larger payloads, and a currency-format change requires a
backend deploy.

---

## What was deliberately not built

Listing these matters as much as the decisions above — an unbounded feature
list is not a design.

- **Discount and promotion engine.** Rules engines are where commerce backends
  go to die. The schema reserves `discount_minor_units` on `orders` so adding
  one does not require a migration on a live table.
- **Full-text search service.** Postgres FTS plus trigram covers a 24-product
  catalogue and would cover a few hundred thousand. Elasticsearch is a second
  system to keep in sync and is not yet earned.
- **Multi-warehouse routing.** `stock_items` is keyed on
  `(variant_id, warehouse_code)` so the data model already supports it; the
  allocation logic picks a single warehouse today.
- **Real payment integration.** Behind a `PaymentGateway` protocol, so the
  sandbox and a real PSP are interchangeable.
- **Admin interface.** The API and permission model support it
  (`require_roles("admin", "staff")`); the UI is out of scope.

---

## What strict CI caught

The pipeline runs `ruff`, `mypy --strict`, `alembic upgrade head` against an
empty database, and `pytest` against a real Postgres. The first time it ran end
to end it found three defects, and not one of them was reachable from a pure
unit test.

**Domain events could not be written at all.** `DomainEvent.to_payload()`
returned `asdict(self)` unmodified, leaving `uuid.UUID` and `datetime` objects
in a dictionary bound for a JSONB column. Every event class here carries at
least one UUID, so the outbox insert failed on all of them - and because that
insert shares a transaction with the state change that produced it, every write
path emitting an event went down with it, reserving stock included.

**Migration 0001 could not run against an empty database.** Both `pg.ENUM`
types were created explicitly with `checkfirst=True` and then a second time,
unguarded, by the `CREATE TABLE` that referenced them. `alembic upgrade head`
stopped on `type "order_status" already exists` at the very first revision -
invisible to anyone whose database was already migrated, fatal to anyone
starting from scratch.

**The concurrency tests never ran.** `tests/integration/` requested a
`seeded_variant_with_one_unit` fixture that was never defined, so both tests
errored during collection rather than failing. A suite that does not run and a
suite that passes look identical to anyone who does not read the output, which
is the argument for a gate that fails the build.

The common thread is that each needed a different kind of execution to surface:
a type checker that refuses to infer `Any`, a migration run against a genuinely
empty database, and a test run against a real one. Any single stage would have
missed the other two.
