import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/routing";
import type { Category } from "@/lib/types";
import { CartBadge } from "./cart-badge";
import { LocaleSwitch } from "./locale-switch";
import { SearchField } from "./search-field";

export async function Header({
  categories,
  locale
}: {
  categories: Category[];
  locale: string;
}) {
  const t = await getTranslations("nav");
  const brand = await getTranslations("brand");

  return (
    <header className="border-b border-[var(--color-rule)] bg-[var(--color-paper)]">
      {/* Trade band. Carries the one promise that changes shopper behaviour,
          in monospace so it reads as a fact rather than a slogan. */}
      <div className="bg-[var(--color-pine)] text-[var(--color-paper)]">
        <p className="mx-auto max-w-[84rem] px-4 py-1.5 font-mono text-[0.6875rem] uppercase tracking-[0.08em]">
          {locale === "sv"
            ? "Fri frakt över 995 kr · 60 dagars öppet köp · Reservdelar i tio år"
            : "Free shipping over 995 kr · 60-day returns · Spare parts for ten years"}
        </p>
      </div>

      <div className="mx-auto flex max-w-[84rem] items-center gap-4 px-4 py-4">
        <Link href="/" className="shrink-0">
          <span className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-[-0.02em]">
            {brand("name")}
          </span>
        </Link>

        <div className="hidden flex-1 md:block">
          <SearchField placeholder={t("search")} />
        </div>

        <div className="ml-auto flex items-center gap-4">
          <LocaleSwitch current={locale} />
          <CartBadge label={t("cart")} />
        </div>
      </div>

      <nav aria-label={t("menu")} className="mx-auto max-w-[84rem] px-4 pb-2">
        <ul className="flex gap-5 overflow-x-auto text-sm">
          {categories.map((category) => (
            <li key={category.path}>
              <Link
                href={`/c/${category.path}`}
                className="inline-block whitespace-nowrap border-b-2 border-transparent py-1 hover:border-[var(--color-pine)]"
              >
                {category.name}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <div className="px-4 pb-3 md:hidden">
        <SearchField placeholder={t("search")} />
      </div>
    </header>
  );
}
