"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { ApiRequestError, browserFetch } from "@/lib/api";
import { useCart } from "./cart-provider";

type Address = {
  id: string;
  recipient: string;
  street: string;
  postal_code: string;
  city: string;
};

type OrderResponse = {
  order_number: string;
  total: { formatted: string };
  payment_redirect_url: string | null;
};

/** Generated once per checkout attempt and reused across retries. */
function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

export function CheckoutForm() {
  const t = useTranslations("checkout");
  const tCart = useTranslations("cart");
  const tErrors = useTranslations();
  const { cart, refresh } = useCart();

  const [addresses, setAddresses] = useState<Address[]>([]);
  const [addressId, setAddressId] = useState("");
  const [method, setMethod] = useState<"standard" | "express" | "pickup">("standard");
  const [idempotencyKey] = useState(newIdempotencyKey);
  const [submitting, setSubmitting] = useState(false);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [order, setOrder] = useState<OrderResponse | null>(null);
  const [signedIn, setSignedIn] = useState(true);

  useEffect(() => {
    void refresh();
    browserFetch<Address[]>("/auth/me/addresses")
      .then((rows) => {
        setAddresses(rows);
        setAddressId(rows[0]?.id ?? "");
      })
      .catch(() => setSignedIn(false));
  }, [refresh]);

  async function placeOrder() {
    setSubmitting(true);
    setErrorKey(null);
    try {
      const result = await browserFetch<OrderResponse>("/checkout", {
        method: "POST",
        // The same key is sent on every retry of this attempt, so a dropped
        // connection replays the original order instead of creating a second.
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({
          shipping_address_id: addressId,
          shipping_method: method,
          accept_price_changes: false
        })
      });
      setOrder(result);
    } catch (error) {
      setErrorKey(
        error instanceof ApiRequestError ? error.messageKey : "errors.generic"
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (order) {
    return (
      <div className="mx-auto max-w-[40rem] px-4 py-24 text-center">
        <p className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-[var(--color-ink-muted)]">
          {order.order_number}
        </p>
        <h1 className="mt-3 font-[family-name:var(--font-display)] text-3xl font-semibold tracking-[-0.02em]">
          Tack. Ordern är mottagen.
        </h1>
        <p className="tnum mt-3 text-[var(--color-ink-muted)]">{order.total.formatted}</p>
      </div>
    );
  }

  if (!signedIn) {
    return (
      <div className="mx-auto max-w-[40rem] px-4 py-24 text-center">
        <h1 className="font-[family-name:var(--font-display)] text-2xl font-semibold">
          {t("signInRequired")}
        </h1>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[84rem] px-4 py-10">
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-[-0.02em]">
        {t("title")}
      </h1>

      <div className="mt-8 grid gap-12 lg:grid-cols-[1fr_22rem]">
        <div className="space-y-10">
          <section>
            <h2 className="font-mono text-[0.6875rem] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
              {t("delivery")}
            </h2>
            <ul className="mt-3 space-y-2">
              {addresses.map((address) => (
                <li key={address.id}>
                  <label className="rule-frame flex cursor-pointer gap-3 px-4 py-3">
                    <input
                      type="radio"
                      name="address"
                      checked={addressId === address.id}
                      onChange={() => setAddressId(address.id)}
                      className="mt-1 accent-[var(--color-pine)]"
                    />
                    <span className="text-sm">
                      <strong className="font-medium">{address.recipient}</strong>
                      <br />
                      {address.street}, {address.postal_code} {address.city}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="font-mono text-[0.6875rem] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
              {t("shippingMethod")}
            </h2>
            <div className="mt-3 space-y-2">
              {(["standard", "express", "pickup"] as const).map((option) => (
                <label key={option} className="rule-frame flex cursor-pointer gap-3 px-4 py-3">
                  <input
                    type="radio"
                    name="method"
                    checked={method === option}
                    onChange={() => setMethod(option)}
                    className="accent-[var(--color-pine)]"
                  />
                  <span className="text-sm">{t(option)}</span>
                </label>
              ))}
            </div>
          </section>
        </div>

        <aside className="rule-frame h-fit p-5 lg:sticky lg:top-6">
          <h2 className="font-mono text-[0.6875rem] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
            {t("summary")}
          </h2>

          {cart ? (
            <dl className="tnum mt-3 space-y-2.5 text-sm">
              <div className="flex justify-between">
                <dt>{tCart("subtotal")}</dt>
                <dd>{cart.subtotal.formatted}</dd>
              </div>
              <div className="flex justify-between">
                <dt>{tCart("shipping")}</dt>
                <dd>
                  {cart.shipping.minor_units === 0
                    ? tCart("freeShipping")
                    : cart.shipping.formatted}
                </dd>
              </div>
              <div className="flex justify-between border-t border-[var(--color-rule)] pt-3 text-base font-medium">
                <dt>{tCart("total")}</dt>
                <dd>{cart.total.formatted}</dd>
              </div>
            </dl>
          ) : null}

          {errorKey ? (
            <p role="alert" className="mt-4 text-sm text-[var(--color-alert)]">
              {tErrors(errorKey as never)}
            </p>
          ) : null}

          <button
            type="button"
            disabled={submitting || !addressId || !cart?.lines.length}
            onClick={() => void placeOrder()}
            className="mt-5 w-full bg-[var(--color-pine)] px-6 py-3.5 font-[family-name:var(--font-display)] text-base text-[var(--color-paper)] hover:bg-[var(--color-pine-bright)] disabled:opacity-40"
          >
            {submitting ? t("processing") : t("placeOrder")}
          </button>
        </aside>
      </div>
    </div>
  );
}
