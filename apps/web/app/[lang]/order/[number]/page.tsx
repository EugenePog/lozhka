import { notFound } from "next/navigation";
import { isLang } from "@/lib/i18n";
import { OrderView } from "@/components/OrderView";

export default async function OrderPage({ params, searchParams }: { params: Promise<{ lang: string; number: string }>; searchParams: Promise<{ token?: string }> }) {
  const { lang, number } = await params;
  if (!isLang(lang)) notFound();
  const { token } = await searchParams;
  return <OrderView number={number} token={token} thanks />;
}
