"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useApp } from "@/lib/context";
import { api } from "@/lib/api";
import { LANGS, LANG_LABEL } from "@/lib/i18n";
import { euro } from "@/lib/money";
import type { Category } from "@/lib/server";

export function Header({ categories }: { categories: Category[] }) {
  const { lang, t, tf, cart, me, logout, minOrder } = useApp();
  const router = useRouter();
  const path = usePathname();
  const [q, setQ] = useState("");
  const [sugg, setSugg] = useState<{ slug: string; name: string }[]>([]);
  const [menu, setMenu] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    clearTimeout(timer.current);
    if (q.trim().length < 2) { setSugg([]); return; }
    timer.current = setTimeout(async () => {
      const { data } = await api.GET("/api/v1/products/suggest", { params: { query: { q, lang } } });
      setSugg((data ?? []) as { slug: string; name: string }[]);
    }, 200);
    return () => clearTimeout(timer.current);
  }, [q, lang]);

  const switchLang = (l: string) => path.replace(/^\/(nl|en|ru)/, `/${l}`) || `/${l}`;
  const count = cart?.item_count ?? 0;

  return (
    <header className="sticky top-0 z-40 bg-cream">
      <div className="bg-green py-1.5 text-center text-xs font-bold text-white">
        <div className="container-page flex items-center justify-between">
          <span>{tf(t.strip, { min: (minOrder / 100).toFixed(0) })}</span>
          <span className="flex gap-3">
            {LANGS.map((l) => (
              <Link key={l} href={switchLang(l)} className={l === lang ? "underline" : "opacity-80 hover:opacity-100"} hrefLang={l}>{LANG_LABEL[l]}</Link>
            ))}
          </span>
        </div>
      </div>
      <div className="border-b border-line">
        <div className="container-page flex items-center gap-4 py-3">
          <Link href={`/${lang}`} className="flex items-center gap-2 text-2xl font-black text-logo" aria-label="Lozhka">🥄 <span>Lozhka</span></Link>
          <form className="relative mx-2 hidden flex-1 md:block" role="search" onSubmit={(e) => { e.preventDefault(); setSugg([]); router.push(`/${lang}/search?q=${encodeURIComponent(q)}`); }}>
            <input className="field pr-12" placeholder={t.searchPlaceholder} aria-label={t.search} value={q} onChange={(e) => setQ(e.target.value)} />
            <button className="absolute right-1 top-1/2 h-10 w-10 -translate-y-1/2 rounded-full text-lg" aria-label={t.search}>🔍</button>
            {sugg.length > 0 && (
              <ul className="card absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden shadow-lg">
                {sugg.map((s) => (
                  <li key={s.slug}><Link href={`/${lang}/p/${s.slug}`} onClick={() => { setSugg([]); setQ(""); }} className="block px-4 py-2 hover:bg-green-tint">{s.name}</Link></li>
                ))}
              </ul>
            )}
          </form>
          <nav className="ml-auto flex items-center gap-1 text-sm font-bold">
            {me ? (
              <div className="relative">
                <button className="flex min-h-target items-center gap-1 rounded-full px-3 hover:bg-green-tint" onClick={() => setMenu((v) => !v)} aria-expanded={menu}>👤 <span className="hidden sm:inline">{tf(t.hello, { name: me.first_name || me.email })}</span></button>
                {menu && (
                  <div className="card absolute right-0 top-full z-50 mt-1 w-48 py-2 shadow-lg" onClick={() => setMenu(false)}>
                    <Link className="block px-4 py-2 hover:bg-green-tint" href={`/${lang}/account`}>{t.account}</Link>
                    <Link className="block px-4 py-2 hover:bg-green-tint" href={`/${lang}/account?tab=favourites`}>{t.favourites}</Link>
                    <button className="block w-full px-4 py-2 text-left hover:bg-green-tint" onClick={async () => { await logout(); router.push(`/${lang}`); }}>{t.logout}</button>
                  </div>
                )}
              </div>
            ) : (
              <Link href={`/${lang}/login`} className="flex min-h-target items-center gap-1 rounded-full px-3 hover:bg-green-tint">👤 {t.login}</Link>
            )}
            <Link href={`/${lang}/cart`} className="relative flex min-h-target items-center gap-1 rounded-full px-3 hover:bg-green-tint" aria-label={t.cart}>
              🛒 <span className="hidden sm:inline">{cart ? euro(cart.subtotal_cents, lang) : t.cart}</span>
              {count > 0 && <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-terra px-1 text-xs text-white" data-testid="cart-count">{count}</span>}
            </Link>
          </nav>
        </div>
        <form className="container-page pb-3 md:hidden" role="search" onSubmit={(e) => { e.preventDefault(); router.push(`/${lang}/search?q=${encodeURIComponent(q)}`); }}>
          <input className="field" placeholder={t.searchPlaceholder} aria-label={t.search} value={q} onChange={(e) => setQ(e.target.value)} />
        </form>
      </div>
      <nav className="border-b border-line bg-cream" aria-label="categories">
        <ul className="container-page flex gap-5 overflow-x-auto py-2 text-sm font-bold">
          <li><Link href={`/${lang}/c/all`} className="whitespace-nowrap hover:text-terra">{t.nav.all}</Link></li>
          {categories.map((c) => (
            <li key={c.slug}>
              <Link href={`/${lang}/c/${c.slug}`} className={`whitespace-nowrap hover:text-terra ${c.kind === "offers" ? "text-terra" : ""}`}>{c.name}</Link>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
