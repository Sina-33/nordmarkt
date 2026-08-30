"use client";

import { usePathname, useRouter } from "@/i18n/routing";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import type { BrandFacet } from "@/lib/types";

export function FacetPanel({ brands }: { brands: BrandFacet[] }) {
  const t = useTranslations("listing");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const active = new Set(searchParams.getAll("brand"));

  function toggle(slug: string) {
    const next = new URLSearchParams(searchParams.toString());
    next.delete("brand");
    // The cursor describes a position in the *old* result set, so any filter
    // change has to drop it or page two comes back nonsensical.
    next.delete("cursor");
    const updated = new Set(active);
    updated.has(slug) ? updated.delete(slug) : updated.add(slug);
    for (const value of updated) next.append("brand", value);
    router.push(`${pathname}?${next.toString()}`, { scroll: false });
  }

  if (brands.length === 0) return null;

  return (
    <aside className="space-y-5">
      <div>
        <h2 className="font-mono text-[0.6875rem] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
          {t("brand")}
        </h2>
        <ul className="mt-2 space-y-1.5">
          {brands.map((brand) => (
            <li key={brand.slug}>
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={active.has(brand.slug)}
                  onChange={() => toggle(brand.slug)}
                  className="h-4 w-4 accent-[var(--color-pine)]"
                />
                <span className="flex-1">{brand.name}</span>
                <span className="tnum font-mono text-xs text-[var(--color-ink-muted)]">
                  {brand.count}
                </span>
              </label>
            </li>
          ))}
        </ul>
      </div>

      {active.size > 0 ? (
        <button
          type="button"
          onClick={() => router.push(pathname, { scroll: false })}
          className="text-sm text-[var(--color-blue)] underline underline-offset-4"
        >
          {t("clear")}
        </button>
      ) : null}
    </aside>
  );
}
