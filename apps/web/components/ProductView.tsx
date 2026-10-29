"use client";
import { useState } from "react";
import { useApp } from "@/lib/context";
import { api } from "@/lib/api";
import { dayFromDate } from "@/lib/money";
import type { Messages } from "@/lib/messages";
import type { Detail, Offers } from "@/lib/server";
import { Crumbs, Heart, Photo, PriceBlock, ProductCard, Qty } from "./ui";

const NUTR: [string, keyof Messages["product"]][] = [
  ["energy_kcal", "energy"], ["fat_g", "fat"], ["saturates_g", "saturates"], ["carbohydrates_g", "carbs"], ["sugars_g", "sugars"], ["fibre_g", "fibre"], ["protein_g", "protein"], ["salt_g", "salt"],
];

export function ProductView({ p, t: _t }: { p: Detail; t: Messages }) {
  const { lang, t, tf, addToCart, cartBusy, cart } = useApp();
  const [qty, setQty] = useState(1);
  const [tab, setTab] = useState(0);
  const [pc, setPc] = useState("");
  const [offers, setOffers] = useState<Offers | null>(null);
  const [email, setEmail] = useState("");
  const [notified, setNotified] = useState(false);
  const out = p.stock_status === "out_of_stock";
  const inCart = cart?.lines.find((l) => l.sku === p.sku)?.qty ?? 0;
  const max = Math.max(0, p.max_qty - inCart);
  const nut = p.nutrition as Record<string, number | string | null> | null;
  const tabs = [t.product.tabDesc, t.product.tabIngr, t.product.tabStorage, t.product.tabDelivery];
  const crumbs = [{ href: `/${lang}`, label: t.list.home }, ...p.category_path.map((c) => ({ href: `/${lang}/c/${c.slug}`, label: String(c.name) })), { label: p.name }];

  async function check() {
    const { data } = await api.GET("/api/v1/delivery/offers", { params: { query: { postcode: pc } } });
    setOffers(data ?? null);
  }
  const first = offers?.slots[0];

  return (
    <>
      <Crumbs items={crumbs} />
      <div className="grid gap-8 md:grid-cols-2">
        <div className="relative">
          <Photo image={p.image} name={p.name} className="aspect-square w-full" size="text-9xl" />
          <div className="absolute right-3 top-3"><Heart sku={p.sku} /></div>
        </div>
        <div>
          <div className="flex flex-wrap gap-2">
            {p.is_discounted && <span className="chip-terra">{t.card.offer}</span>}
            {p.tags.includes("bestseller") && <span className="chip">{t.card.bestseller}</span>}
            {p.storage_type === "frozen" && <span className="chip">{t.card.frozen}</span>}
          </div>
          <h1 className="mt-2">{p.name}</h1>
          <div className="text-muted">{[p.brand, p.unit_label].filter(Boolean).join(" · ")}</div>
          <p className="mt-3">{p.short_description}</p>
          <div className="mt-4"><PriceBlock p={p} large /></div>
          <div className={`mt-2 text-sm font-bold ${out ? "text-terra" : "text-green"}`}>
            {out ? t.card.outOfStock : p.stock_status === "low_stock" ? t.card.lowStock : t.card.inStock}
          </div>
          {out ? (
            <div id="notify" className="card mt-4 p-4">
              {notified ? <p className="font-bold">{t.product.notifyDone}</p> : (
                <form className="flex gap-2" onSubmit={async (e) => { e.preventDefault(); await api.POST("/api/v1/products/{sku}/notify", { params: { path: { sku: p.sku } }, body: { email, lang } }); setNotified(true); }}>
                  <input type="email" required className="field" placeholder={t.product.notifyEmail} value={email} onChange={(e) => setEmail(e.target.value)} />
                  <button className="btn">{t.card.notify}</button>
                </form>
              )}
            </div>
          ) : (
            <div className="mt-5 flex flex-wrap items-center gap-4">
              <Qty value={qty} max={Math.max(1, max)} onChange={(n) => setQty(Math.max(1, n))} />
              <button className="btn flex-1 sm:flex-none" disabled={cartBusy || max <= 0} onClick={async () => { if (await addToCart(p.sku, qty)) setQty(1); }}>{max <= 0 ? t.card.limit : t.product.addToCart}</button>
            </div>
          )}
          <div className="card mt-6 p-4">
            <div className="mb-2 font-extrabold">{t.product.checkPostcode}</div>
            <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); void check(); }}>
              <input className="field" placeholder="1012 AB" aria-label={t.product.postcode} value={pc} onChange={(e) => setPc(e.target.value)} />
              <button className="btn-outline">{t.product.check}</button>
            </form>
            {offers && (
              <p className={`mt-2 text-sm font-bold ${offers.in_zone && first ? "" : "text-terra"}`}>
                {offers.in_zone && first ? tf(t.product.deliverNext, { day: dayFromDate(first.delivery_date, lang), from: first.deliver_from, to: first.deliver_to }) : t.product.noDelivery}
              </p>
            )}
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-1 text-sm">
            {p.country_of_origin ? (<><dt className="text-muted">{t.product.origin}</dt><dd className="font-bold">{p.country_of_origin}</dd></>) : null}
            {p.brand ? (<><dt className="text-muted">{t.product.brand}</dt><dd className="font-bold">{p.brand}</dd></>) : null}
          </dl>
        </div>
      </div>

      <div className="mt-10">
        <div role="tablist" className="flex gap-2 overflow-x-auto border-b border-line">
          {tabs.map((label, i) => (
            <button key={label} role="tab" aria-selected={tab === i} onClick={() => setTab(i)} className={`whitespace-nowrap border-b-4 px-4 py-3 font-extrabold ${tab === i ? "border-terra text-terra" : "border-transparent"}`}>{label}</button>
          ))}
        </div>
        <div role="tabpanel" className="card mt-4 p-6">
          {tab === 0 && (
            <div className="space-y-3">
              <p className="whitespace-pre-line">{p.description || t.product.noInfo}</p>
              {p.allergens.length > 0 && (
                <div>
                  {(["contains", "may_contain"] as const).map((k) => {
                    const list = p.allergens.filter((a) => a.presence === k);
                    return list.length ? <p key={k}><b>{k === "contains" ? t.product.contains : t.product.mayContain}:</b> {list.map((a) => String(a.name)).join(", ")}</p> : null;
                  })}
                </div>
              )}
            </div>
          )}
          {tab === 1 && (
            <div className="space-y-4">
              <p>{p.ingredients || t.product.noInfo}</p>
              {nut && (
                <table className="w-full max-w-md text-sm">
                  <caption className="mb-1 text-left text-muted">{tf(t.product.nutritionPer, { basis: String(nut.basis ?? "100 g") })}</caption>
                  <tbody>
                    {NUTR.filter(([k]) => nut[k] != null).map(([k, label]) => (
                      <tr key={k} className="border-t border-line"><td className="py-1">{t.product[label]}</td><td className="py-1 text-right font-bold">{String(nut[k])}</td></tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
          {tab === 2 && <p>{p.storage_instructions || t.product.noInfo}</p>}
          {tab === 3 && <p>{t.product.deliveryText}</p>}
        </div>
      </div>

      {p.related.length > 0 && (
        <section className="mt-12">
          <h2 className="mb-4">{t.product.related}</h2>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">{p.related.slice(0, 4).map((r) => <ProductCard key={r.sku} p={r} />)}</div>
        </section>
      )}
    </>
  );
}
