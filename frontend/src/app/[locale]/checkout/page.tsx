import { setRequestLocale } from "next-intl/server";
import { CheckoutForm } from "@/components/checkout-form";

export default async function CheckoutPage({
  params
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <CheckoutForm />;
}
