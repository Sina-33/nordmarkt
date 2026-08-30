import { getTranslations, setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/routing";
import { ProductGrid } from "@/components/product-grid";
import { getCategories, listProducts } from "@/lib/catalog";

export default async function HomePage({
  params
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("home");
  // Both fetches are independent, so they run concurrently rather than
  // serialising two round trips into the render.
  const [newest, popular, categories] = await Promise.all([
    listProducts(locale, { sort: "newest", limit: 8 }),
    listProducts(locale, { sort: "rating", limit: 4 }),
    getCategories(locale)
  ]);

  const hero = newest.data[0];

  return (
    <div className="mx-auto max-w-[84rem] px-4">
      {/* The hero is the thesis: a statement of what the shop refuses to sell,
          set against the single most characteristic product photograph. */}
      <section className="grid gap-8 border-b border-[var(--color-rule)] py-12 lg:grid-cols-[1.1fr_1fr] lg:py-16">
        <div className="flex flex-col justify-center">
          <p className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-[var(--color-ink-muted)]">
            {t("kicker")}
          </p>
          <h1 className="mt-4 font-[family-name:var(--font-display)] text-4xl font-semibold leading-[1.05] tracking-[-0.03em] sm:text-5xl lg:text-6xl">
            {t("heading")}
          </h1>
          <p className="mt-5 max-w-[46ch] text-[1.0625rem] leading-relaxed text-[var(--color-ink-muted)]">
            {t("body")}
          </p>
          <div className="mt-7">
            <Link
              href="/c/hem"
              className="inline-block bg-[var(--color-ink)] px-7 py-3.5 font-[family-name:var(--font-display)] text-base text-[var(--color-paper)] transition-colors hover:bg-[var(--color-pine)]"
            >
              {t("browse")}
            </Link>
          </div>
        </div>

        {hero?.image ? (
          <Link href={`/p/${hero.slug}`} className="rule-frame relative block aspect-[4/3]">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={hero.image.url}
              alt={hero.image.alt}
              className="absolute inset-0 h-full w-full object-cover"
            />
            <span className="absolute bottom-0 left-0 bg-[var(--color-paper)] px-3 py-2 font-mono text-[0.6875rem] uppercase tracking-[0.08em]">
              {hero.title} · {hero.price_from.formatted}
            </span>
          </Link>
        ) : null}
      </section>

      <section className="py-12">
        <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-[-0.02em]">
          {t("newArrivals")}
        </h2>
        <div className="mt-6">
          <ProductGrid products={newest.data} />
        </div>
      </section>

      <section className="border-t border-[var(--color-rule)] py-12">
        <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-[-0.02em]">
          {t("shopByRoom")}
        </h2>
        <ul className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {categories.flatMap((parent) =>
            parent.children.map((child) => (
              <li key={child.path}>
                <Link
                  href={`/c/${child.path}`}
                  className="rule-frame flex items-baseline justify-between px-4 py-4 transition-colors hover:bg-[var(--color-sand)]"
                >
                  <span className="font-[family-name:var(--font-display)] text-lg">
                    {child.name}
                  </span>
                  <span className="font-mono text-[0.6875rem] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
                    {parent.name}
                  </span>
                </Link>
              </li>
            ))
          )}
        </ul>
      </section>

      <section className="border-t border-[var(--color-rule)] py-12">
        <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-[-0.02em]">
          {t("popular")}
        </h2>
        <div className="mt-6">
          <ProductGrid products={popular.data} />
        </div>
      </section>
    </div>
  );
}
