import { notFound } from "next/navigation";
import { AppProvider } from "@/lib/context";
import { isLang } from "@/lib/i18n";
import { sget, type Category } from "@/lib/server";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { Toasts } from "@/components/ui";

export default async function LangLayout({ children, params }: { children: React.ReactNode; params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const [cats, settings] = await Promise.all([
    sget<Category[]>(`/categories?lang=${lang}`, 60),
    sget<Record<string, unknown>>("/settings", 60),
  ]);
  const minOrder = Number(settings?.min_order_cents ?? 5000);
  return (
    <AppProvider lang={lang} minOrder={minOrder}>
      <div lang={lang} className="flex min-h-screen flex-col">
        <Header categories={cats ?? []} />
        <main className="container-page flex-1 py-6">{children}</main>
        <Footer lang={lang} />
        <Toasts />
      </div>
    </AppProvider>
  );
}
