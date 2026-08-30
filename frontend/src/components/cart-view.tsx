"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { useCart } from "./cart-provider";

export function CartView() {
  const t = useTranslations("cart");
  const { cart, refresh, setQuantity, pending } = useCart();

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (!cart || cart.lines.length === 0) {
    return (
      <div className="mx-auto max-w-[40rem] px-4 py-24 text-center">
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-[-0.02em]">
          {t("empty")}
        </h1>
        <p className="mt-3 text-[var(--color-ink-muted)]">{t("emptyHint")}</p>
        <Link
          href="/"
          className="mt-7 inline-block bg-[var(--color-ink)] px-7 py-3 text-[var(--color-paper)]"
        >
          {t("keepShopping")}
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[84rem] px-4 py-10">
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-[-0.02em]">
        {t("title")}
      </h1>

      {cart.free_shipping_remaining ? (
        <p className="mt-3 border-l-2 border-[var(--color-pine)] pl-3 font-mono text-xs uppercase tracking-[0.08em]">
          {t("freeShippingProgress", { amount: cart.free_shipping_remaining.formatted })}
        </p>
      ) : null}

      <div className="mt-8 grid gap-12 lg:grid-cols-[1fr_22rem]">
        <ul className="divide-y divide-[var(--color-rule)] border-y border-[var(--color-rule)]">
          {cart.lines.map((line) => (
            <li key={line.variant_id} className="flex gap-4 py-5">
              {line.image_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={line.image_url}
                  alt=""
                  className="rule-frame h-28 w-24 shrink-0 object-cover"
                />
              ) : null}

              <div className="flex-1">
                <p className="font-[family-name:var(--font-display)] text-lg leading-tight">
                  {line.title}
                </p>
                {Object.keys(line.options).length > 0 ? (
                  <p className="mt-0.5 text-sm text-[var(--color-ink-muted)]">
                    {Object.values(line.options).join(" · ")}
                  </p>
                ) : null}

                {line.price_changed ? (
                  <p className="mt-1 text-sm text-[var(--color-alert)]">
                    {t("priceChanged")}
                  </p>
                ) : null}

                <div className="mt-3 flex items-center gap-3">
                  <label className="sr-only" htmlFor={`qty-${line.variant_id}`}>
                    {t("quantity")}
                  </label>
                  <input
                    id={`qty-${line.variant_id}`}
                    type="number"
                    min={0}
                    max={99}
                    value={line.quantity}
                    disabled={pending}
                    onChange={(event) =>
                      void setQuantity(line.variant_id, Number(event.target.value))
                    }
                    className="tnum w-16 border border-[var(--color-rule)] bg-[var(--color-paper-raised)] px-2 py-1.5 text-sm"
                  />
                  <button
                    type="button"
                    onClick={() => void setQuantity(line.variant_id, 0)}
                    className="text-sm text-[var(--color-blue)] underline underline-offset-4"
                  >
                    {t("remove")}
                  </button>
                </div>

                <p className="spec-strip mt-3">
                  <span>SKU {line.sku}</span>
                  <span className="tnum">{line.unit_price.formatted} / st</span>
                </p>
              </div>

              <p className="tnum shrink-0 font-medium">{line.line_total.formatted}</p>
            </li>
          ))}
        </ul>

        <aside className="rule-frame h-fit p-5 lg:sticky lg:top-6">
          <dl className="tnum space-y-2.5 text-sm">
            <div className="flex justify-between">
              <dt>{t("subtotal")}</dt>
              <dd>{cart.subtotal.formatted}</dd>
            </div>
            <div className="flex justify-between">
              <dt>{t("shipping")}</dt>
              <dd>
                {cart.shipping.minor_units === 0 ? t("freeShipping") : cart.shipping.formatted}
              </dd>
            </div>
            <div className="flex justify-between text-[var(--color-ink-muted)]">
              <dt>{t("vat")}</dt>
              <dd>{cart.vat_included.formatted}</dd>
            </div>
            <div className="flex justify-between border-t border-[var(--color-rule)] pt-3 text-base font-medium">
              <dt>{t("total")}</dt>
              <dd>{cart.total.formatted}</dd>
            </div>
          </dl>

          <Link
            href="/checkout"
            className="mt-5 block bg-[var(--color-pine)] px-6 py-3.5 text-center font-[family-name:var(--font-display)] text-base text-[var(--color-paper)] hover:bg-[var(--color-pine-bright)]"
          >
            {t("checkout")}
          </Link>
        </aside>
      </div>
    </div>
  );
}
