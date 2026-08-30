import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { NextIntlClientProvider, hasLocale } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Familjen_Grotesk, IBM_Plex_Mono, Inter } from "next/font/google";

import { Footer } from "@/components/footer";
import { Header } from "@/components/header";
import { CartProvider } from "@/components/cart-provider";
import { getCategories } from "@/lib/catalog";
import { routing } from "@/i18n/routing";
import "./globals.css";

// Familjen Grotesk is a Swedish typeface commissioned for public signage.
// Using it for display type ties the storefront to the market it serves rather
// than to a generic geometric sans.
const familjen = Familjen_Grotesk({
  subsets: ["latin"],
  variable: "--font-familjen",
  display: "swap"
});
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
  display: "swap"
});

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "brand" });

  return {
    title: { default: `${t("name")} — ${t("tagline")}`, template: `%s · ${t("name")}` },
    description: t("tagline"),
    // Hreflang pairs so each market's URL is the canonical one for that market.
    alternates: {
      canonical: `/${locale}`,
      languages: { sv: "/sv", en: "/en" }
    }
  };
}

export default async function LocaleLayout({
  children,
  params
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();

  // Opts this subtree into static rendering; without it every page falls back
  // to dynamic rendering the moment a translation is read.
  setRequestLocale(locale);

  const categories = await getCategories(locale);

  return (
    <html
      lang={locale}
      className={`${familjen.variable} ${inter.variable} ${plexMono.variable}`}
    >
      <body className="min-h-screen flex flex-col antialiased">
        <NextIntlClientProvider>
          <CartProvider>
            <a
              href="#main"
              className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-3 focus:bg-ink focus:px-4 focus:py-2 focus:text-paper"
            >
              Hoppa till innehåll
            </a>
            <Header categories={categories} locale={locale} />
            <main id="main" className="flex-1">
              {children}
            </main>
            <Footer />
          </CartProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
