import Link from "next/link";
import { notFound } from "next/navigation";
import { isLang } from "@/lib/i18n";
import { messages } from "@/lib/messages";
import { sget } from "@/lib/server";
import type { Schemas } from "@lozhka/api-client";
import { ProductCard, Photo } from "@/components/ui";
import { Newsletter } from "@/components/Newsletter";

export default async function Home({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const t = messages[lang];
  const home = await sget<Schemas["HomeOut"]>(`/home?lang=${lang}`);
  if (!home) return <p>{t.common.error}</p>;
  const section = (title: string, items: Schemas["ProductCard"][], href: string) =>
    items.length === 0 ? null : (
      <section className="mt-12">
        <div className="mb-4 flex items-end justify-between"><h2>{title}</h2><Link href={href} className="link">{t.home.seeAll} →</Link></div>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-5">{items.slice(0, 5).map((p) => <ProductCard key={p.sku} p={p} />)}</div>
      </section>
    );
  const tops = home.categories.filter((c) => c.kind !== "offers");
  return (
    <>
      <section className="grid items-center gap-6 rounded-card bg-green-tint p-8 md:grid-cols-2 md:p-12">
        <div>
          <h1>{home.hero?.title ?? "Lozhka"}</h1>
          <p className="mt-3 text-lg">{home.hero?.body_markdown}</p>
          <Link href={`/${lang}/c/all`} className="btn mt-6">{t.home.shopNow}</Link>
        </div>
        <div className="hidden justify-center gap-3 text-7xl md:flex" aria-hidden>🥛🥟🐟</div>
      </section>
      <ul className="mt-6 grid gap-3 sm:grid-cols-3">
        {home.usps.map((u) => (
          <li key={u.slug} className="card p-4"><div className="font-extrabold">{u.title}</div><div className="text-sm text-muted">{u.body_markdown}</div></li>
        ))}
      </ul>
      <section className="mt-12">
        <h2 className="mb-4">{t.home.categories}</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {tops.map((c) => (
            <Link key={c.slug} href={`/${lang}/c/${c.slug}`} className="card p-3 text-center font-extrabold transition hover:shadow-md">
              <Photo name={c.slug} className="mb-2 aspect-[4/3] w-full" size="text-4xl" />
              {c.name}
            </Link>
          ))}
        </div>
      </section>
      {section(t.home.offers, home.offers, `/${lang}/c/offers`)}
      {section(t.home.bestsellers, home.bestsellers, `/${lang}/c/all?tag=bestseller`)}
      {section(t.home.newItems, home.new_items, `/${lang}/c/all?tag=new`)}
      <section className="mt-12">
        <h2 className="mb-4">{t.home.how}</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          {[[t.home.how1, t.home.how1d, "🛒"], [t.home.how2, t.home.how2d, "📦"], [t.home.how3, t.home.how3d, "🚐"]].map(([a, b, e]) => (
            <div key={a} className="card p-5"><div className="text-3xl">{e}</div><div className="mt-2 font-extrabold">{a}</div><div className="text-sm text-muted">{b}</div></div>
          ))}
        </div>
      </section>
      <Newsletter />
    </>
  );
}
