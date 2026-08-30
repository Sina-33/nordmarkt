import Image from "next/image";
import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/routing";
import type { ProductSummary } from "@/lib/types";

export async function ProductCard({
  product,
  priority = false
}: {
  product: ProductSummary;
  priority?: boolean;
}) {
  const t = await getTranslations("product");
  const discounted =
    product.compare_at !== null &&
    product.compare_at.minor_units > product.price_from.minor_units;

  return (
    <article className="group flex flex-col">
      <Link href={`/p/${product.slug}`} className="block">
        <div className="rule-frame relative aspect-[4/5] overflow-hidden">
          {product.image ? (
            <Image
              src={product.image.url}
              alt={product.image.alt}
              fill
              // Explicit sizes stop Next serving a 1000px file into a 240px
              // slot on mobile, which is most of the LCP budget on a listing.
              sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 22vw"
              priority={priority}
              className="object-cover transition-transform duration-300 group-hover:scale-[1.03]"
            />
          ) : null}
          {discounted ? (
            <span className="absolute left-0 top-0 bg-[var(--color-alert)] px-2 py-1 font-mono text-[0.625rem] uppercase tracking-[0.08em] text-white">
              −
              {Math.round(
                (1 - product.price_from.minor_units / product.compare_at!.minor_units) * 100
              )}
              %
            </span>
          ) : null}
        </div>
      </Link>

      <div className="mt-3 flex flex-1 flex-col">
        {product.brand ? (
          <p className="font-mono text-[0.6875rem] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
            {product.brand}
          </p>
        ) : null}

        <h3 className="mt-0.5 font-[family-name:var(--font-display)] text-[1.0625rem] leading-tight">
          <Link href={`/p/${product.slug}`}>{product.title}</Link>
        </h3>

        <div className="tnum mt-2 flex items-baseline gap-2">
          <span className="text-base font-medium">{product.price_from.formatted}</span>
          {discounted ? (
            <span className="text-xs text-[var(--color-ink-muted)] line-through">
              {product.compare_at!.formatted}
            </span>
          ) : null}
        </div>

        {/* Signature spec strip: the same warehouse-label row that appears on
            the product page, the cart and the order confirmation. */}
        <div className="spec-strip mt-3">
          <span className="tnum">
            {product.rating_average} / 5 ({product.rating_count})
          </span>
          <span>{t("shipsFrom")} SE</span>
        </div>
      </div>
    </article>
  );
}
