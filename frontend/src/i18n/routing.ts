import { defineRouting } from "next-intl/routing";
import { createNavigation } from "next-intl/navigation";

/**
 * Swedish is the default and English is the secondary market, but neither is
 * implicit: every URL carries its locale (`/sv/...`, `/en/...`). A prefixless
 * default would leave the same content on two addresses, and Google would pick
 * one of them for us.
 */
export const routing = defineRouting({
  locales: ["sv", "en"],
  defaultLocale: "sv",
  localePrefix: "always",
  localeDetection: true
});

export type Locale = (typeof routing.locales)[number];

export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);
