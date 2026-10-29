import { notFound } from "next/navigation";
import { isLang } from "@/lib/i18n";
import { Listing, type Sp } from "@/components/Listing";

export default async function Category({ params, searchParams }: { params: Promise<{ lang: string; slug: string }>; searchParams: Promise<Sp> }) {
  const { lang, slug } = await params;
  if (!isLang(lang)) notFound();
  return <Listing lang={lang} slug={slug} sp={await searchParams} />;
}
