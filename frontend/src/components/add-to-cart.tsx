"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import type { Variant } from "@/lib/types";
import { useCart } from "./cart-provider";

export function AddToCart({ variants }: { variants: Variant[] }) {
  const t = useTranslations("product");
  const tErrors = useTranslations();
  const { addItem, pending, lastErrorKey } = useCart();

  const [selectedId, setSelectedId] = useState(variants[0]?.id ?? "");
  const [confirmed, setConfirmed] = useState(false);

  const selected = variants.find((v) => v.id === selectedId) ?? variants[0];
  if (!selected) return null;

  const sellable = selected.sellable ?? 0;
  const soldOut = sellable <= 0;
  const optionKeys = Object.keys(selected.options);

  return (
    <div className="space-y-4">
      {variants.length > 1 && optionKeys.length > 0 ? (
        <fieldset>
          <legend className="font-mono text-[0.6875rem] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
            {t("chooseVariant")}
          </legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {variants.map((variant) => {
              const label = Object.values(variant.options).join(" · ");
              const unavailable = (variant.sellable ?? 0) <= 0;
              return (
                <button
                  key={variant.id}
                  type="button"
                  onClick={() => setSelectedId(variant.id)}
                  aria-pressed={variant.id === selectedId}
                  className={[
                    "border px-3 py-2 text-sm",
                    variant.id === selectedId
                      ? "border-[var(--color-ink)] bg-[var(--color-ink)] text-[var(--color-paper)]"
                      : "border-[var(--color-rule)] hover:bg-[var(--color-sand)]",
                    unavailable ? "opacity-40" : ""
                  ].join(" ")}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </fieldset>
      ) : null}

      <p className="tnum font-mono text-xs uppercase tracking-[0.08em]">
        {soldOut
          ? t("outOfStock")
          : sellable <= 5
            ? t("lowStock", { count: sellable })
            : t("inStock", { count: sellable })}
      </p>

      <button
        type="button"
        disabled={soldOut || pending}
        onClick={async () => {
          try {
            await addItem(selected.id, 1);
            setConfirmed(true);
            window.setTimeout(() => setConfirmed(false), 2000);
          } catch {
            setConfirmed(false);
          }
        }}
        className="w-full bg-[var(--color-pine)] px-6 py-3.5 font-[family-name:var(--font-display)] text-base text-[var(--color-paper)] transition-colors hover:bg-[var(--color-pine-bright)] disabled:cursor-not-allowed disabled:opacity-40"
      >
        {pending ? t("adding") : confirmed ? t("added") : t("addToCart")}
      </button>

      {/* Errors name what happened and what to do; they do not apologise. */}
      {lastErrorKey ? (
        <p role="alert" className="text-sm text-[var(--color-alert)]">
          {tErrors(lastErrorKey as never)}
        </p>
      ) : null}

      <p className="spec-strip">
        <span>
          SKU {selected.sku}
        </span>
        <span>{t("vatIncluded")}</span>
      </p>
    </div>
  );
}
