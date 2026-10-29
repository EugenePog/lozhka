"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useApp } from "@/lib/context";
import { api } from "@/lib/api";
import { euro, formatDateTime } from "@/lib/money";
import type { Schemas } from "@lozhka/api-client";
import { ProductCard } from "@/components/ui";

type Addr = Schemas["AddressOut"];
const BLANK: Schemas["AddressIn"] = { label: "", first_name: "", last_name: "", street: "", house_number: "", addition: "", postcode: "", city: "", delivery_notes: "", is_default: false };

function Account() {
  const { lang, t, tf, me, meLoaded, refreshMe, toast, cart, refreshCart } = useApp();
  const router = useRouter();
  const tab = useSearchParams().get("tab") ?? "orders";
  const [orders, setOrders] = useState<Schemas["OrderSummary"][]>([]);
  const [favs, setFavs] = useState<Schemas["ProductCard"][]>([]);
  const [addrs, setAddrs] = useState<Addr[]>([]);
  const [edit, setEdit] = useState<(Schemas["AddressIn"] & { id?: number }) | null>(null);
  const [det, setDet] = useState({ first_name: "", last_name: "", phone: "", language: lang as string });

  const load = useCallback(async () => {
    const [o, f, a] = await Promise.all([api.GET("/api/v1/me/orders"), api.GET("/api/v1/me/favourites/products", { params: { query: { lang } } }), api.GET("/api/v1/me/addresses")]);
    setOrders(o.data ?? []); setFavs(f.data ?? []); setAddrs(a.data ?? []);
  }, [lang]);
  useEffect(() => { if (meLoaded && !me) router.replace(`/${lang}/login`); if (me) { void load(); setDet({ first_name: me.first_name, last_name: me.last_name, phone: me.phone, language: me.language }); } }, [me, meLoaded, lang, router, load]);
  if (!me) return <p>{t.common.loading}</p>;
  const a = t.accountPage;
  const tabs: [string, string][] = [["orders", a.orders], ["favourites", a.favourites], ["addresses", a.addresses], ["details", a.details], ["payments", a.payments]];

  async function reorder(number: string) {
    const { data } = await api.GET("/api/v1/orders/{number}", { params: { path: { number } } });
    if (!data) return;
    const skipped: string[] = [];
    for (const l of data.lines) {
      const { error } = await api.POST("/api/v1/cart/items", { body: { sku: l.sku, qty: l.qty } });
      if (error) skipped.push(l.name);
    }
    await refreshCart();
    toast(skipped.length ? tf(a.reorderSkipped, { items: skipped.join(", ") }) : a.reordered, skipped.length ? "err" : "ok");
    if (!skipped.length) router.push(`/${lang}/cart`);
  }
  void cart;

  return (
    <>
      <h1 className="mb-1 text-3xl">{a.title}</h1>
      <p className="mb-4 text-muted">{me.email} · {orders.length} {a.stats.orders} · {favs.length} {a.stats.favourites} · {addrs.length} {a.stats.addresses}</p>
      <div role="tablist" className="mb-6 flex gap-2 overflow-x-auto border-b border-line">
        {tabs.map(([k, label]) => <Link key={k} role="tab" aria-selected={tab === k} href={`/${lang}/account?tab=${k}`} className={`whitespace-nowrap border-b-4 px-4 py-3 font-extrabold ${tab === k ? "border-terra text-terra" : "border-transparent"}`}>{label}</Link>)}
      </div>

      {tab === "orders" && (orders.length === 0 ? <p>{a.noOrders}</p> : (
        <ul className="space-y-3">
          {orders.map((o) => (
            <li key={o.order_number} className="card flex flex-wrap items-center justify-between gap-3 p-4">
              <div>
                <div className="font-extrabold">{o.order_number} <span className="chip ml-2">{t.order.status[o.status as keyof typeof t.order.status] ?? o.status}</span></div>
                <div className="text-sm text-muted">{formatDateTime(o.placed_at, lang)} · {o.item_count} · {euro(o.total_cents, lang)}</div>
              </div>
              <div className="flex gap-2">
                <Link className="btn-outline btn-sm" href={`/${lang}/order/${o.order_number}`}>{a.details2}</Link>
                <button className="btn btn-sm" onClick={() => reorder(o.order_number)}>{a.reorder}</button>
              </div>
            </li>
          ))}
        </ul>
      ))}

      {tab === "favourites" && (favs.length === 0 ? <p>{a.noFav}</p> : <div className="grid grid-cols-2 gap-4 md:grid-cols-4">{favs.map((p) => <ProductCard key={p.sku} p={p} />)}</div>)}

      {tab === "addresses" && (
        <div className="space-y-3">
          {addrs.length === 0 && !edit && <p>{a.noAddr}</p>}
          {addrs.map((x) => (
            <div key={x.id} className="card flex flex-wrap items-center justify-between gap-3 p-4">
              <div><b>{x.label || `${x.first_name} ${x.last_name}`}</b> {x.is_default && <span className="chip ml-1">{a.default}</span>}<br />{x.street} {x.house_number}{x.addition}, {x.postcode} {x.city}</div>
              <div className="flex gap-2">
                <button className="btn-outline btn-sm" onClick={() => setEdit(x)}>{a.edit}</button>
                <button className="btn-outline btn-sm" onClick={async () => { await api.DELETE("/api/v1/me/addresses/{address_id}", { params: { path: { address_id: x.id } } }); await load(); }}>{a.delete}</button>
              </div>
            </div>
          ))}
          {edit ? (
            <form className="card grid gap-3 p-5 sm:grid-cols-2" onSubmit={async (e) => {
              e.preventDefault();
              const { id, ...body } = edit;
              if (id) await api.PUT("/api/v1/me/addresses/{address_id}", { params: { path: { address_id: id } }, body });
              else await api.POST("/api/v1/me/addresses", { body });
              setEdit(null); await load(); toast(a.saved);
            }}>
              {([["label", a.label], ["first_name", t.checkout.firstName], ["last_name", t.checkout.lastName], ["street", t.checkout.street], ["house_number", t.checkout.houseNumber], ["addition", t.checkout.addition], ["postcode", t.checkout.postcode], ["city", t.checkout.city]] as const).map(([k, label]) => (
                <div key={k}><label className="label">{label}</label><input className="field" required={k !== "label" && k !== "addition"} value={String(edit[k] ?? "")} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })} /></div>
              ))}
              <label className="flex items-center gap-2 text-sm font-bold sm:col-span-2"><input type="checkbox" checked={edit.is_default} onChange={(e) => setEdit({ ...edit, is_default: e.target.checked })} /> {a.default}</label>
              <div className="flex gap-2 sm:col-span-2"><button className="btn">{a.save}</button><button type="button" className="btn-outline" onClick={() => setEdit(null)}>{t.common.close}</button></div>
            </form>
          ) : <button className="btn" onClick={() => setEdit({ ...BLANK, is_default: addrs.length === 0 })}>{a.add}</button>}
        </div>
      )}

      {tab === "details" && (
        <form className="card grid max-w-xl gap-3 p-5" onSubmit={async (e) => { e.preventDefault(); await api.PATCH("/api/v1/me", { body: det }); await refreshMe(); toast(a.saved); }}>
          <div><label className="label">{t.checkout.firstName}</label><input className="field" value={det.first_name} onChange={(e) => setDet({ ...det, first_name: e.target.value })} /></div>
          <div><label className="label">{t.checkout.lastName}</label><input className="field" value={det.last_name} onChange={(e) => setDet({ ...det, last_name: e.target.value })} /></div>
          <div><label className="label">{t.checkout.phone}</label><input className="field" value={det.phone} onChange={(e) => setDet({ ...det, phone: e.target.value })} /></div>
          <div><label className="label">{a.language}</label><select className="field" value={det.language} onChange={(e) => setDet({ ...det, language: e.target.value })}><option value="nl">Nederlands</option><option value="en">English</option><option value="ru">Русский</option></select></div>
          <button className="btn w-fit">{a.save}</button>
        </form>
      )}

      {tab === "payments" && <p className="card p-5">{a.paymentsNote}</p>}
    </>
  );
}

export default function AccountPage() {
  return <Suspense><Account /></Suspense>;
}
