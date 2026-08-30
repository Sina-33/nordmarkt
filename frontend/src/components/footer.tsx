import { getTranslations } from "next-intl/server";

export async function Footer() {
  const t = await getTranslations("footer");
  const brand = await getTranslations("brand");

  return (
    <footer className="mt-16 border-t border-[var(--color-rule)] bg-[var(--color-pine)] text-[var(--color-paper)]">
      <div className="mx-auto grid max-w-[84rem] gap-8 px-4 py-10 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <p className="font-[family-name:var(--font-display)] text-xl font-semibold">
            {brand("name")}
          </p>
          <p className="mt-1 text-sm opacity-70">{brand("tagline")}</p>
        </div>
        <ul className="space-y-2 text-sm">
          <li>{t("shipping")}</li>
          <li>{t("spareParts")}</li>
          <li>{t("contact")}</li>
          <li>{t("terms")}</li>
        </ul>
        <div className="lg:col-span-2">
          <p className="font-mono text-[0.6875rem] uppercase tracking-[0.08em] opacity-70">
            {t("note")}
          </p>
        </div>
      </div>
    </footer>
  );
}
