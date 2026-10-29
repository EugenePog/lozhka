import Link from "next/link";
import { messages, fmt } from "@/lib/messages";
import { sget, type Category } from "@/lib/server";
import type { Lang } from "@/lib/i18n";
import type { Schemas } from "@lozhka/api-client";
import { ProductCard, Crumbs } from "./ui";

export type Sp = Record<string, string | undefined>;

export async function Listing({ lang, slug, sp, query }: { lang: Lang; slug?: string; sp: Sp; query?: string }) {
  const t = messages[lang];
  const cats = (await sget<Category[]>(`/categories?lang=${lang}`, 60)) ?? [];
  const flat = cats.flatMap((c) => [c, ...c.children]);
  const cat = slug && slug !== "all" ? flat.find((c) => c.slug === slug) : undefined;
  const page = Math.max(1, Number(sp.page ?? 1));
  const params = new URLSearchParams({ lang, page: String(page), sort: sp.sort ?? "relevance" });
  if (cat) params.set(cat.kind === "offers" ? "offers" : "category", cat.kind === "offers" ? "true" : cat.slug);
  if (query) params.set("q", query);
  if (sp.tag) params.set("tag", sp.tag);
  if (sp.storage) params.set("tag", sp.storage === "frozen" ? "frozen" : sp.tag ?? "");
  if (sp.in_stock) params.set("in_stock", "true");
  const list = await sget<Schemas["ProductList"]>(`/products?${params}`);
  const base = (over: Sp) => {
    const merged: Sp = { ...sp, ...over };
    const qs = new URLSearchParams(Object.entries(merged).filter(([k, v]) => v && k !== "slug" && !(k === "page" && v === "1")) as [string, string][]);
    if (query) qs.set("q", query);
    const path = query ? `/${lang}/search` : `/${lang}/c/${slug ?? "all"}`;
    return qs.toString() ? `${path}?${qs}` : path;
  };
  const sorts: [string, string][] = [["relevance", t.list.relevance], ["price_asc", t.list.priceAsc], ["price_desc", t.list.priceDesc], ["new", t.list.newest]];
  const parent = cat?.parent_slug ? flat.find((c) => c.slug === cat.parent_slug) : undefined;
  const sideRoot = (parent ?? cat) ?? undefined;
  return (
    <>
      <Crumbs items={[{ href: `/${lang}`, label: t.list.home }, ...(parent ? [{ href: `/${lang}/c/${parent.slug}`, label: parent.name }] : []), { label: query ? fmt(t.list.searchResults, { q: query }) : cat?.name ?? t.nav.all }]} />
      <div className="grid gap-8 lg:grid-cols-[240px_1fr]">
        <aside className="space-y-6">
          <div>
            <h3 className="mb-2 font-extrabold">{t.list.categories}</h3>
            <ul className="space-y-1 text-sm">
              <li><Link href={`/${lang}/c/all`} className={!cat ? "font-black text-terra" : ""}>{t.nav.all}</Link></li>
              {cats.map((c) => (
                <li key={c.slug}>
                  <Link href={`/${lang}/c/${c.slug}`} className={cat?.slug === c.slug ? "font-black text-terra" : ""}>{c.name} <span className="text-muted">({c.product_count})</span></Link>
                  {sideRoot?.slug === c.slug && c.children.length > 0 && (
                    <ul className="ml-3 mt-1 space-y-1">{c.children.map((ch) => <li key={ch.slug}><Link href={`/${lang}/c/${ch.slug}`} className={cat?.slug === ch.slug ? "font-black text-terra" : ""}>{ch.name}</Link></li>)}</ul>
                  )}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="mb-2 font-extrabold">{t.list.filters}</h3>
            <ul className="space-y-1 text-sm">
              <li><Link href={base({ in_stock: sp.in_stock ? undefined : "1", page: "1" })} className="flex items-center gap-2"><span className={`inline-block h-4 w-4 rounded border border-form-line ${sp.in_stock ? "bg-green" : ""}`} />{t.list.inStock}</Link></li>
              <li><Link href={base({ tag: sp.tag === "frozen" ? undefined : "frozen", page: "1" })} className="flex items-center gap-2"><span className={`inline-block h-4 w-4 rounded border border-form-line ${sp.tag === "frozen" ? "bg-green" : ""}`} />{t.list.frozen}</Link></li>
              <li><Link href={base({ tag: undefined, in_stock: undefined, sort: undefined, page: "1" })} className="link">{t.list.reset}</Link></li>
            </ul>
          </div>
        </aside>
        <section>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div><h1 className="text-3xl">{query ? fmt(t.list.searchResults, { q: query }) : cat?.name ?? t.nav.all}</h1><div className="text-sm text-muted">{fmt(t.list.products, { n: list?.total ?? 0 })}</div></div>
            <div className="flex flex-wrap gap-2" role="group" aria-label={t.list.sort}>
              {sorts.map(([k, label]) => <Link key={k} href={base({ sort: k, page: "1" })} className={`rounded-full px-3 py-1 text-sm font-bold ${(sp.sort ?? "relevance") === k ? "bg-green text-white" : "bg-green-tint"}`}>{label}</Link>)}
            </div>
          </div>
          {!list || list.items.length === 0 ? (
            <div className="card p-10 text-center"><div className="text-5xl">🔎</div><h2 className="mt-2">{t.list.empty}</h2><p className="text-muted">{t.list.emptyHint}</p></div>
          ) : (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">{list.items.map((p) => <ProductCard key={p.sku} p={p} />)}</div>
          )}
          {list && list.pages > 1 && (
            <nav className="mt-8 flex items-center justify-center gap-2" aria-label="pagination">
              {page > 1 && <Link className="btn-outline btn-sm" href={base({ page: String(page - 1) })}>{t.list.prev}</Link>}
              <span className="text-sm font-bold">{page} / {list.pages}</span>
              {page < list.pages && <Link className="btn-outline btn-sm" href={base({ page: String(page + 1) })}>{t.list.next}</Link>}
            </nav>
          )}
        </section>
      </div>
    </>
  );
}
