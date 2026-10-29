"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useApp } from "@/lib/context";
import { api, problemOf } from "@/lib/api";
import { countdown, dayFromDate, euro } from "@/lib/money";
import type { Offers, Slot } from "@/lib/server";
import { Stepper } from "@/components/ui";

type Form = { email: string; phone: string; first_name: string; last_name: string; street: string; house_number: string; addition: string; postcode: string; city: string; notes: string };
const EMPTY: Form = { email: "", phone: "", first_name: "", last_name: "", street: "", house_number: "", addition: "", postcode: "", city: "", notes: "" };
const POSTCODE = /^[1-9][0-9]{3}\s?[A-Za-z]{2}$/;

export default function Checkout() {
  const { lang, t, tf, cart, me, minOrder } = useApp();
  const router = useRouter();
  const [f, setF] = useState<Form>(EMPTY);
  const [offers, setOffers] = useState<Offers | null>(null);
  const [choice, setChoice] = useState<"asap" | string>("asap"); // "asap" or "TEMPLATE|DATE"
  const [method, setMethod] = useState("card_on_delivery");
  const [terms, setTerms] = useState(false);
  const [marketing, setMarketing] = useState(false);
  const [save, setSave] = useState(false);
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [formErr, setFormErr] = useState("");
  const [busy, setBusy] = useState(false);

  // Prefill from the account once.
  useEffect(() => {
    if (!me) return;
    setF((x) => ({ ...x, email: x.email || me.email, phone: x.phone || me.phone, first_name: x.first_name || me.first_name, last_name: x.last_name || me.last_name }));
    void api.GET("/api/v1/me/addresses").then(({ data }) => {
      const a = data?.find((i) => i.is_default) ?? data?.[0];
      if (a) setF((x) => (x.street ? x : { ...x, first_name: a.first_name, last_name: a.last_name, street: a.street, house_number: a.house_number, addition: a.addition, postcode: a.postcode, city: a.city, notes: a.delivery_notes }));
    });
  }, [me]);

  const pcOk = POSTCODE.test(f.postcode.trim());
  useEffect(() => {
    if (!pcOk) { setOffers(null); return; }
    let live = true;
    void api.GET("/api/v1/delivery/offers", { params: { query: { postcode: f.postcode } } }).then(({ data }) => { if (live) { setOffers(data ?? null); setChoice("asap"); } });
    return () => { live = false; };
  }, [f.postcode, pcOk]);

  const sub = cart ? cart.subtotal_cents - cart.discount_cents : 0;
  const feeFor = useMemo(() => {
    const tier = offers?.fee_tiers.find((x) => sub >= x.min_subtotal_cents && (x.max_subtotal_cents == null || sub < x.max_subtotal_cents));
    return tier?.fee_cents ?? 0;
  }, [offers, sub]);

  if (!cart) return <p>{t.common.loading}</p>;
  if (cart.lines.length === 0) return <p>{t.cartPage.empty} <Link href={`/${lang}/c/all`} className="link">{t.cartPage.toShop}</Link></p>;

  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF((x) => ({ ...x, [k]: e.target.value }));
  const inp = (k: keyof Form, label: string, extra: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <div>
      <label className="label" htmlFor={k}>{label}</label>
      <input id={k} name={k} className="field" value={f[k]} onChange={set(k)} aria-invalid={!!errs[k]} {...extra} />
      {errs[k] && <p className="err">{errs[k]}</p>}
    </div>
  );
  const slots = offers?.slots ?? [];
  const asap = offers?.asap;
  const picked: Slot | undefined = choice === "asap" ? asap ?? undefined : slots.find((s) => `${s.template_code}|${s.delivery_date}` === choice);
  const slotLabel = (s: Slot) => `${dayFromDate(s.delivery_date, lang)}, ${s.deliver_from}–${s.deliver_to}`;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const er: Record<string, string> = {};
    const req: (keyof Form)[] = ["email", "first_name", "last_name", "street", "house_number", "postcode", "city"];
    if (method === "card_on_delivery") req.push("phone");
    for (const k of req) if (!f[k].trim()) er[k] = t.checkout.required;
    if (f.email && !/^\S+@\S+\.\S+$/.test(f.email)) er.email = t.checkout.errors.email_invalid;
    if (f.postcode && !pcOk) er.postcode = t.checkout.required;
    if (!picked) er.delivery = t.checkout.errors.delivery_required;
    if (!terms) er.terms = t.checkout.errors.terms_required;
    setErrs(er);
    if (Object.keys(er).length) { setFormErr(t.checkout.fixErrors); return; }
    setFormErr(""); setBusy(true);
    const { data, error } = await api.POST("/api/v1/checkout", {
      body: { ...f, delivery_choice: choice === "asap" ? "asap" : "time_range", template_code: picked!.template_code, delivery_date: picked!.delivery_date, payment_method: method, terms_accepted: terms, marketing_opt_in: marketing, save_address: save && !!me, language: lang },
    });
    setBusy(false);
    if (data) { router.push(data.pay_url ? data.pay_url : `/${lang}/order/${data.order_number}?token=${data.token}`); return; }
    const p = problemOf(error);
    const msgs = t.checkout.errors as Record<string, string>;
    setFormErr(tf(msgs[p.code] ?? msgs.unknown, { min: (minOrder / 100).toFixed(0) }));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const radio = (active: boolean) => `flex cursor-pointer items-start gap-3 rounded-input border-2 p-3 ${active ? "border-terra bg-terra-tint" : "border-line bg-card"}`;
  return (
    <form onSubmit={submit} noValidate>
      <Stepper step={2} />
      <Link href={`/${lang}/cart`} className="link text-sm">← {t.checkout.back}</Link>
      <h1 className="mb-4 mt-2 text-3xl">{t.checkout.title}</h1>
      {formErr && <div role="alert" className="mb-4 rounded-input bg-terra-tint p-3 font-bold text-terra-tint-text">{formErr}</div>}
      <div className="grid gap-8 lg:grid-cols-[1fr_380px]">
        <div className="space-y-6">
          <section className="card space-y-3 p-5">
            <h2 className="text-xl">{t.checkout.contact}</h2>
            {inp("email", t.checkout.email, { type: "email", autoComplete: "email" })}
            {!me && <p className="text-sm text-muted">{t.checkout.haveAccount} <Link className="link" href={`/${lang}/login?next=checkout`}>{t.checkout.loginLink}</Link></p>}
            {inp("phone", method === "card_on_delivery" ? t.checkout.phoneReq : t.checkout.phone, { type: "tel", autoComplete: "tel" })}
          </section>
          <section className="card space-y-3 p-5">
            <h2 className="text-xl">{t.checkout.address}</h2>
            <div className="grid gap-3 sm:grid-cols-2">{inp("first_name", t.checkout.firstName, { autoComplete: "given-name" })}{inp("last_name", t.checkout.lastName, { autoComplete: "family-name" })}</div>
            <div className="grid gap-3 sm:grid-cols-[1fr_120px_120px]">{inp("street", t.checkout.street, { autoComplete: "address-line1" })}{inp("house_number", t.checkout.houseNumber)}{inp("addition", t.checkout.addition)}</div>
            <div className="grid gap-3 sm:grid-cols-[160px_1fr]">{inp("postcode", t.checkout.postcode, { autoComplete: "postal-code", placeholder: "1012 AB" })}{inp("city", t.checkout.city, { autoComplete: "address-level2" })}</div>
            <div><label className="label" htmlFor="notes">{t.checkout.notes}</label><textarea id="notes" className="field" rows={2} value={f.notes} onChange={set("notes")} /></div>
            {me && <label className="flex items-center gap-2 text-sm font-bold"><input type="checkbox" checked={save} onChange={(e) => setSave(e.target.checked)} /> {t.checkout.saveAddress}</label>}
          </section>
          <section className="card space-y-3 p-5">
            <h2 className="text-xl">{t.checkout.time}</h2>
            {!pcOk ? <p className="text-muted">{t.checkout.enterPostcode}</p> : offers && !offers.in_zone ? <p className="err">{t.checkout.outside}</p> : slots.length === 0 && !asap ? <p className="text-muted">{t.checkout.noSlots}</p> : (
              <>
                {asap && (
                  <label className={radio(choice === "asap")}>
                    <input type="radio" name="slot" checked={choice === "asap"} onChange={() => setChoice("asap")} className="mt-1" />
                    <span><b>{t.checkout.asap}</b> — {slotLabel(asap)}<br /><span className="text-sm text-muted">{tf(t.checkout.orderBy, { t: countdown(asap.order_by) })}</span></span>
                  </label>
                )}
                <div className="text-sm font-bold text-muted">{t.checkout.orChoose}</div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {slots.map((s) => {
                    const key = `${s.template_code}|${s.delivery_date}`;
                    return (
                      <label key={key} className={`${radio(choice === key)} ${s.is_full ? "opacity-50" : ""}`}>
                        <input type="radio" name="slot" disabled={s.is_full} checked={choice === key} onChange={() => setChoice(key)} className="mt-1" />
                        <span><b>{slotLabel(s)}</b>{s.is_full ? <span className="chip-terra ml-2">{t.checkout.full}</span> : null}</span>
                      </label>
                    );
                  })}
                </div>
              </>
            )}
            {errs.delivery && <p className="err">{errs.delivery}</p>}
          </section>
          <section className="card space-y-3 p-5">
            <h2 className="text-xl">{t.checkout.payment}</h2>
            {([["ideal", t.checkout.ideal], ["card", t.checkout.card], ["card_on_delivery", t.checkout.cod]] as const).map(([k, label]) => (
              <label key={k} className={radio(method === k)}>
                <input type="radio" name="pay" checked={method === k} onChange={() => setMethod(k)} className="mt-1" />
                <span><b>{label}</b>{k === "card_on_delivery" && method === k ? <><br /><span className="text-sm text-muted">{t.checkout.codNote}</span></> : null}</span>
              </label>
            ))}
          </section>
          <section className="space-y-2">
            <label className="flex items-start gap-2 font-bold"><input type="checkbox" className="mt-1" checked={terms} onChange={(e) => setTerms(e.target.checked)} /> {t.checkout.terms}</label>
            {errs.terms && <p className="err">{errs.terms}</p>}
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={marketing} onChange={(e) => setMarketing(e.target.checked)} /> {t.checkout.marketing}</label>
          </section>
        </div>
        <aside className="card h-fit p-5 lg:sticky lg:top-40">
          <h2 className="mb-3 text-xl">{t.checkout.summary}</h2>
          <ul className="space-y-1 text-sm">{cart.lines.map((l) => <li key={l.sku} className="flex justify-between gap-2"><span>{l.qty} × {l.name}</span><span className="font-bold">{euro(l.line_total_cents, lang)}</span></li>)}</ul>
          <dl className="mt-3 space-y-1 border-t border-line pt-3">
            <div className="flex justify-between"><dt>{t.cartPage.subtotal}</dt><dd>{euro(cart.subtotal_cents, lang)}</dd></div>
            {cart.discount_cents > 0 && <div className="flex justify-between text-terra"><dt>{t.cartPage.discount}</dt><dd>−{euro(cart.discount_cents, lang)}</dd></div>}
            <div className="flex justify-between"><dt>{t.checkout.deliveryFee}</dt><dd>{offers?.in_zone ? (feeFor === 0 ? t.checkout.free : euro(feeFor, lang)) : "—"}</dd></div>
            <div className="flex justify-between border-t border-line pt-2 text-lg font-black"><dt>{t.cartPage.total}</dt><dd>{euro(sub + (offers?.in_zone ? feeFor : 0), lang)}</dd></div>
          </dl>
          <button className="btn mt-4 w-full" disabled={busy}>{method === "card_on_delivery" ? t.checkout.place : t.checkout.placeAndPay}</button>
        </aside>
      </div>
    </form>
  );
}
