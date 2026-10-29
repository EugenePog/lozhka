"use client";
import Link from "next/link";
import { useState } from "react";
import { useApp } from "@/lib/context";
import { euro } from "@/lib/money";
import { Photo, Qty, Stepper } from "@/components/ui";

export default function CartPage() {
  const { lang, t, tf, cart, setQty, removeLine, applyPromo, minOrder } = useApp();
  const [code, setCode] = useState("");
  if (!cart) return <p>{t.common.loading}</p>;
  if (cart.lines.length === 0)
    return (
      <div className="card mx-auto max-w-lg p-10 text-center">
        <div className="text-6xl">🛒</div><h1 className="mt-2 text-3xl">{t.cartPage.empty}</h1><p className="text-muted">{t.cartPage.emptyHint}</p>
        <Link href={`/${lang}/c/all`} className="btn mt-6">{t.cartPage.toShop}</Link>
      </div>
    );
  const blocked = cart.lines.some((l) => l.problem === "out_of_stock" || l.problem === "unavailable") && cart.lines.every((l) => l.problem);
  const below = cart.shortfall_cents > 0;
  const promoErr = cart.promo_error ? (t.cartPage.errors as Record<string, string>)[cart.promo_error] ?? cart.promo_error : "";
  return (
    <>
      <Stepper step={1} />
      <h1 className="mb-4 text-3xl">{t.cartPage.title}</h1>
      <div className="grid gap-8 lg:grid-cols-[1fr_380px]">
        <ul className="space-y-3">
          {cart.lines.map((l) => (
            <li key={l.sku} className={`card flex gap-4 p-3 ${l.problem ? "border-terra" : ""}`} data-sku={l.sku}>
              <Photo image={l.image} name={l.name} className="h-24 w-24 shrink-0" size="text-3xl" />
              <div className="flex flex-1 flex-col justify-between gap-2 sm:flex-row sm:items-center">
                <div>
                  <Link href={`/${lang}/p/${l.slug}`} className="font-extrabold hover:underline">{l.name}</Link>
                  <div className="text-sm text-muted">{l.unit_label} · {euro(l.unit_price_cents, lang)}</div>
                  {l.problem && <div className="text-sm font-bold text-terra">{l.problem === "out_of_stock" ? t.cartPage.problemOut : l.problem === "reduced" ? tf(t.cartPage.problemReduced, { n: l.max_qty }) : t.cartPage.problemGone}</div>}
                </div>
                <div className="flex items-center gap-4">
                  <Qty value={l.qty} max={l.max_qty} onChange={(n) => (n <= 0 ? removeLine(l.sku) : setQty(l.sku, n))} />
                  <div className="w-20 text-right font-black">{euro(l.line_total_cents, lang)}</div>
                  <button className="min-h-target min-w-target text-muted hover:text-terra" aria-label={t.cartPage.remove} onClick={() => removeLine(l.sku)}>✕</button>
                </div>
              </div>
            </li>
          ))}
          <li className="flex justify-between text-sm">
            <Link href={`/${lang}/c/all`} className="link">← {t.cartPage.continue}</Link>
          </li>
        </ul>
        <aside className="card h-fit p-5">
          <form className="mb-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); void applyPromo(code); }}>
            <input className="field" placeholder={t.cartPage.promo} aria-label={t.cartPage.promo} value={code} onChange={(e) => setCode(e.target.value)} />
            <button className="btn-outline">{t.cartPage.apply}</button>
          </form>
          {cart.promo_code && !promoErr && <p className="mb-2 text-sm font-bold text-green">✓ {tf(t.cartPage.promoApplied, { code: cart.promo_code })} <button className="link ml-2" onClick={() => applyPromo("")}>✕</button></p>}
          {promoErr && <p className="err mb-2">{promoErr}</p>}
          <dl className="space-y-2">
            <div className="flex justify-between"><dt>{t.cartPage.subtotal}</dt><dd className="font-bold">{euro(cart.subtotal_cents, lang)}</dd></div>
            {cart.discount_cents > 0 && <div className="flex justify-between text-terra"><dt>{t.cartPage.discount}</dt><dd className="font-bold">−{euro(cart.discount_cents, lang)}</dd></div>}
            <div className="flex justify-between"><dt>{t.cartPage.delivery}</dt><dd className="text-sm text-muted">{t.cartPage.calcAtCheckout}</dd></div>
            <div className="flex justify-between border-t border-line pt-2 text-lg font-black"><dt>{t.cartPage.total}</dt><dd>{euro(cart.subtotal_cents - cart.discount_cents, lang)}</dd></div>
          </dl>
          <div className="mt-3">
            <div className="h-2 overflow-hidden rounded-full bg-green-tint"><div className="h-full bg-green" style={{ width: `${Math.min(100, ((cart.subtotal_cents - cart.discount_cents) / Math.max(1, minOrder)) * 100)}%` }} /></div>
            <p className={`mt-1 text-sm font-bold ${below ? "text-terra" : "text-green"}`}>{below ? tf(t.cartPage.minHint, { amount: (cart.shortfall_cents / 100).toFixed(2), min: (minOrder / 100).toFixed(0) }) : t.cartPage.minReached}</p>
          </div>
          {below || blocked ? <button className="btn mt-4 w-full" disabled>{t.cartPage.checkout}</button> : <Link href={`/${lang}/checkout`} className="btn mt-4 w-full">{t.cartPage.checkout}</Link>}
        </aside>
      </div>
    </>
  );
}
