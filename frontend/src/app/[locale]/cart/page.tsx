import { setRequestLocale } from "next-intl/server";
import { CartView } from "@/components/cart-view";

export default async function CartPage({
  params
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <CartView />;
}
