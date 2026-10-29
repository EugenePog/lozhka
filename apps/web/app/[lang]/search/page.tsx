import { notFound } from "next/navigation";
import { isLang } from "@/lib/i18n";
import { Listing, type Sp } from "@/components/Listing";

export default async function Search({ params, searchParams }: { params: Promise<{ lang: string }>; searchParams: Promise<Sp> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const sp = await searchParams;
  return <Listing lang={lang} sp={sp} query={sp.q ?? ""} />;
}
