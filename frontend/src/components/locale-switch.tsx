"use client";

import { useTransition } from "react";
import { usePathname, useRouter } from "@/i18n/routing";
import { routing } from "@/i18n/routing";

export function LocaleSwitch({ current }: { current: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const [pending, startTransition] = useTransition();

  return (
    <div className="flex font-mono text-xs" role="group" aria-label="Language">
      {routing.locales.map((locale, index) => (
        <button
          key={locale}
          type="button"
          disabled={pending || locale === current}
          aria-current={locale === current ? "true" : undefined}
          onClick={() =>
            // Swapping language must keep the shopper on the same page, not
            // bounce them to the homepage - usePathname already carries the
            // current route's resolved dynamic segments.
            startTransition(() => {
              router.replace(pathname, { locale, scroll: false });
            })
          }
          className={[
            "px-2 py-1 uppercase",
            index === 0 ? "border" : "border border-l-0",
            "border-[var(--color-rule)]",
            locale === current
              ? "bg-[var(--color-ink)] text-[var(--color-paper)]"
              : "hover:bg-[var(--color-sand)]"
          ].join(" ")}
        >
          {locale}
        </button>
      ))}
    </div>
  );
}
