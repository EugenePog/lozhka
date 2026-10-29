"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useApp } from "@/lib/context";
import { api } from "@/lib/api";
import { euro, formatDateTime, formatTime } from "@/lib/money";
import type { Order } from "@/lib/server";
import { Stepper } from "./ui";

const STEP_OF: Record<string, number> = { awaiting_payment: 0, pending_confirmation: 0, paid: 1, confirmed: 1, picking: 2, packed: 2, out_for_delivery: 3, delivered: 4 };
const DEAD = ["cancelled", "payment_failed", "delivery_failed", "refunded"];

export function OrderView({ number, token, thanks = false }: { number: string; token?: string; thanks?: boolean }) {
  const { lang, t, tf, refreshCart } = useApp();
  const [o, setO] = useState<Order | null>(null);
  const [missing, setMissing] = useState(false);
  const load = useCallback(async () => {
    const { data, response } = await api.GET("/api/v1/orders/{number}", { params: { path: { number }, query: { token } } });
    if (data) setO(data); else if (response.status === 404 || response.status === 403) setMissing(true);
  }, [number, token]);
  useEffect(() => { void load(); void refreshCart(); const i = setInterval(load, 20000); return () => clearInterval(i); }, [load, refreshCart]);

  if (missing) return <p>{t.common.error}</p>;
  if (!o) return <p>{t.common.loading}</p>;
  const step = STEP_OF[o.status] ?? 0;
  const dead = DEAD.includes(o.status);
  const steps = [t.order.steps.awaiting_confirmation, t.order.steps.confirmed, t.order.steps.packing, t.order.steps.on_the_way, t.order.steps.delivered];
  const cod = o.payment_method === "card_on_delivery";
  return (
    <>
      {thanks && <Stepper step={3} />}
      <div className="card p-6 text-center">
        <div className="text-5xl">{dead ? "😕" : "✅"}</div>
        <h1 className="mt-2 text-3xl">{dead ? t.order.status[o.status as keyof typeof t.order.status] : tf(t.order.thanks, { name: o.ship_name.split(" ")[0] })}</h1>
        <p className="text-muted">{o.status === "awaiting_payment" ? t.order.awaitingPayment : tf(t.order.thanksSub, { n: o.order_number })}</p>
        {o.status === "pending_confirmation" && o.confirm_deadline_at && <p className="mt-1 font-bold">{tf(t.order.codSub, { t: formatTime(o.confirm_deadline_at, lang) })}</p>}
        {o.status === "awaiting_payment" && <Link className="btn mt-4" href={`/pay/test/${o.order_number}?token=${o.token}`}>{t.checkout.placeAndPay}</Link>}
      </div>
      {!dead && (
        <ol className="mt-6 grid grid-cols-5 gap-2 text-center text-xs font-bold sm:text-sm" aria-label="status">
          {steps.map((s, i) => (
            <li key={s}>
              <div className={`mx-auto mb-1 flex h-9 w-9 items-center justify-center rounded-full ${i <= step ? "bg-green text-white" : "bg-green-tint"}`}>{i < step ? "✓" : i + 1}</div>
              <span className={i <= step ? "" : "text-muted"}>{s}</span>
            </li>
          ))}
        </ol>
      )}
      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <section className="card p-5">
          <h2 className="mb-2 text-xl">{t.order.delivery}</h2>
          <p className="font-bold">{o.ship_name}</p>
          <p>{o.ship_address}<br />{o.ship_postcode} {o.ship_city}</p>
          {o.delivery_window_from && o.delivery_window_to && <p className="mt-2 font-bold">{formatDateTime(o.delivery_window_from, lang)} – {formatTime(o.delivery_window_to, lang)}</p>}
          <h2 className="mb-1 mt-4 text-xl">{t.order.payment}</h2>
          <p>{t.order.method[o.payment_method as keyof typeof t.order.method] ?? o.payment_method}{cod ? ` — ${t.order.payAtDoor}` : ""}</p>
        </section>
        <section className="card p-5">
          <h2 className="mb-2 text-xl">{t.order.summary} · {o.order_number}</h2>
          <ul className="space-y-1 text-sm">{o.lines.map((l) => <li key={l.sku} className="flex justify-between gap-2"><span>{l.qty} × {l.name}</span><span className="font-bold">{euro(l.line_total_cents, lang)}</span></li>)}</ul>
          <dl className="mt-3 space-y-1 border-t border-line pt-3 text-sm">
            <div className="flex justify-between"><dt>{t.cartPage.subtotal}</dt><dd>{euro(o.subtotal_cents, lang)}</dd></div>
            {o.discount_cents > 0 && <div className="flex justify-between text-terra"><dt>{t.cartPage.discount}</dt><dd>−{euro(o.discount_cents, lang)}</dd></div>}
            <div className="flex justify-between"><dt>{t.checkout.deliveryFee}</dt><dd>{o.delivery_fee_cents ? euro(o.delivery_fee_cents, lang) : t.checkout.free}</dd></div>
            <div className="flex justify-between text-lg font-black"><dt>{t.cartPage.total}</dt><dd>{euro(o.total_cents, lang)}</dd></div>
          </dl>
        </section>
      </div>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        {o.can_cancel && <button className="btn-outline" onClick={async () => { if (confirm(t.order.cancelConfirm)) { await api.POST("/api/v1/orders/{number}/cancel", { params: { path: { number }, query: { token } } }); await load(); } }}>{t.order.cancel}</button>}
        <Link href={`/${lang}/c/all`} className="btn">{t.order.continue}</Link>
      </div>
    </>
  );
}
