"use client";

import { useEffect } from "react";
import { Link } from "@/i18n/routing";
import { useCart } from "./cart-provider";

export function CartBadge({ label }: { label: string }) {
  const { itemCount, refresh } = useCart();

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <Link href="/cart" className="flex items-center gap-2 text-sm" aria-label={label}>
      <span className="hidden sm:inline">{label}</span>
      <span
        className="tnum inline-flex h-6 min-w-6 items-center justify-center border border-[var(--color-ink)] px-1.5 font-mono text-xs"
        aria-live="polite"
      >
        {itemCount}
      </span>
    </Link>
  );
}
