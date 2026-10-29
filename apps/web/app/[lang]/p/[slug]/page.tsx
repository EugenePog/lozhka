import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { isLang } from "@/lib/i18n";
import { messages } from "@/lib/messages";
import { sget, type Detail } from "@/lib/server";
import { ProductView } from "@/components/ProductView";

type P = { params: Promise<{ lang: string; slug: string }> };

export async function generateMetadata({ params }: P): Promise<Metadata> {
  const { lang, slug } = await params;
  const p = await sget<Detail>(`/products/${slug}?lang=${lang}`);
  return { title: p?.name ?? "Lozhka", description: p?.short_description };
}

export default async function ProductPage({ params }: P) {
  const { lang, slug } = await params;
  if (!isLang(lang)) notFound();
  const p = await sget<Detail>(`/products/${slug}?lang=${lang}`);
  if (!p) notFound();
  return <ProductView p={p} t={messages[lang]} />;
}
