import { getTranslations, setRequestLocale } from "next-intl/server";
import { FacetPanel } from "@/components/facet-panel";
import { ProductGrid } from "@/components/product-grid";
import { listProducts } from "@/lib/catalog";

export default async function SearchPage({
  params,
  searchParams
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const query = await searchParams;
  const t = await getTranslations("listing");
  const term = typeof query.q === "string" ? query.q : "";
  const brands = query.brand
    ? Array.isArray(query.brand)
      ? query.brand
      : [query.brand]
    : [];

  const result = await listProducts(locale, { q: term, brand: brands });

  return (
    <div className="mx-auto max-w-[84rem] px-4 py-8">
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-[-0.02em]">
        {term}
      </h1>
      <p className="tnum mt-1 font-mono text-xs uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
        {t("results", { count: result.meta.total })}
      </p>

      <div className="mt-8 grid gap-10 lg:grid-cols-[15rem_1fr]">
        <FacetPanel brands={result.facets.brands} />
        {result.data.length === 0 ? (
          <div className="rule-frame px-6 py-16 text-center">
            <p className="font-[family-name:var(--font-display)] text-xl">{t("empty")}</p>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">{t("emptyHint")}</p>
          </div>
        ) : (
          <ProductGrid products={result.data} />
        )}
      </div>
    </div>
  );
}
