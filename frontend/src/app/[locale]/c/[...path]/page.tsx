import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { FacetPanel } from "@/components/facet-panel";
import { ProductGrid } from "@/components/product-grid";
import { Link } from "@/i18n/routing";
import { listProducts } from "@/lib/catalog";
import { ApiRequestError } from "@/lib/api";

type Props = {
  params: Promise<{ locale: string; path: string[] }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function CategoryPage({ params, searchParams }: Props) {
  const { locale, path } = await params;
  setRequestLocale(locale);

  const query = await searchParams;
  const t = await getTranslations("listing");

  // The URL segments *are* the materialised path the API filters on, so
  // /c/hem/mobler/sittmobler maps to "hem.mobler.sittmobler" with no lookup.
  const categoryPath = path.join(".");
  const brands = query.brand
    ? Array.isArray(query.brand)
      ? query.brand
      : [query.brand]
    : [];

  let result;
  try {
    result = await listProducts(locale, {
      category: categoryPath,
      brand: brands,
      sort: typeof query.sort === "string" ? query.sort : undefined,
      cursor: typeof query.cursor === "string" ? query.cursor : undefined
    });
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) notFound();
    throw error;
  }

  return (
    <div className="mx-auto max-w-[84rem] px-4 py-8">
      <nav aria-label="Breadcrumb" className="font-mono text-[0.6875rem] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
        {path.map((segment, index) => (
          <span key={segment}>
            {index > 0 ? " / " : ""}
            <Link href={`/c/${path.slice(0, index + 1).join("/")}`}>{segment}</Link>
          </span>
        ))}
      </nav>

      <div className="mt-4 flex items-baseline justify-between">
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-[-0.02em]">
          {path.at(-1)}
        </h1>
        <p className="tnum font-mono text-xs uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
          {t("results", { count: result.meta.total })}
        </p>
      </div>

      <div className="mt-8 grid gap-10 lg:grid-cols-[15rem_1fr]">
        <FacetPanel brands={result.facets.brands} />

        {result.data.length === 0 ? (
          <div className="rule-frame px-6 py-16 text-center">
            <p className="font-[family-name:var(--font-display)] text-xl">{t("empty")}</p>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">{t("emptyHint")}</p>
          </div>
        ) : (
          <div>
            <ProductGrid products={result.data} />
            {result.meta.next_cursor ? (
              <div className="mt-12 text-center">
                <Link
                  href={`/c/${path.join("/")}?cursor=${result.meta.next_cursor}`}
                  className="inline-block border border-[var(--color-ink)] px-8 py-3 text-sm hover:bg-[var(--color-sand)]"
                >
                  {t("loadMore")}
                </Link>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
