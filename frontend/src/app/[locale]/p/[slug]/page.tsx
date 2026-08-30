import type { Metadata } from "next";
import Image from "next/image";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { AddToCart } from "@/components/add-to-cart";
import { ApiRequestError } from "@/lib/api";
import { getProduct } from "@/lib/catalog";

type Props = { params: Promise<{ locale: string; slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, slug } = await params;
  try {
    const product = await getProduct(locale, slug);
    return {
      title: product.title,
      description: product.description.slice(0, 160),
      openGraph: {
        title: product.title,
        description: product.description.slice(0, 160),
        images: product.images[0] ? [{ url: product.images[0].url }] : []
      }
    };
  } catch {
    return { title: "404" };
  }
}

export default async function ProductPage({ params }: Props) {
  const { locale, slug } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("product");

  let product;
  try {
    product = await getProduct(locale, slug);
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) notFound();
    throw error;
  }

  // Product structured data. Google reads price and availability from here,
  // so it is generated from the same objects the page renders rather than
  // hand-maintained alongside them.
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.title,
    description: product.description,
    sku: product.variants[0]?.sku,
    brand: product.brand ? { "@type": "Brand", name: product.brand } : undefined,
    image: product.images.map((image) => image.url),
    aggregateRating:
      product.rating_count > 0
        ? {
            "@type": "AggregateRating",
            ratingValue: product.rating_average,
            reviewCount: product.rating_count
          }
        : undefined,
    offers: product.variants.map((variant) => ({
      "@type": "Offer",
      sku: variant.sku,
      price: variant.price.amount,
      priceCurrency: variant.price.currency,
      availability:
        (variant.sellable ?? 0) > 0
          ? "https://schema.org/InStock"
          : "https://schema.org/OutOfStock"
    }))
  };

  return (
    <article className="mx-auto max-w-[84rem] px-4 py-8">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <div className="grid gap-10 lg:grid-cols-[1.15fr_1fr]">
        <div className="space-y-3">
          {product.images.map((image, index) => (
            <div key={image.url} className="rule-frame relative aspect-[4/5]">
              <Image
                src={image.url}
                alt={image.alt}
                fill
                sizes="(max-width: 1024px) 100vw, 55vw"
                priority={index === 0}
                className="object-cover"
              />
            </div>
          ))}
        </div>

        <div className="lg:sticky lg:top-6 lg:self-start">
          {product.brand ? (
            <p className="font-mono text-[0.6875rem] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
              {product.brand}
            </p>
          ) : null}

          <h1 className="mt-1 font-[family-name:var(--font-display)] text-3xl font-semibold leading-tight tracking-[-0.02em] sm:text-4xl">
            {product.title}
          </h1>

          <div className="tnum mt-4 flex items-baseline gap-3">
            <span className="text-2xl font-medium">{product.price_from.formatted}</span>
            {product.compare_at ? (
              <span className="text-sm text-[var(--color-ink-muted)]">
                {t("was")} <s>{product.compare_at.formatted}</s>
              </span>
            ) : null}
          </div>

          <p className="mt-5 leading-relaxed text-[var(--color-ink-muted)]">
            {product.description}
          </p>

          {product.highlights.length > 0 ? (
            <ul className="mt-5 space-y-1.5 text-sm">
              {product.highlights.map((highlight) => (
                <li key={highlight} className="flex gap-2">
                  <span aria-hidden="true" className="text-[var(--color-pine)]">
                    —
                  </span>
                  {highlight}
                </li>
              ))}
            </ul>
          ) : null}

          <div className="mt-8">
            <AddToCart variants={product.variants} />
          </div>
        </div>
      </div>
    </article>
  );
}
