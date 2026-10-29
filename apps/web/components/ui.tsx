"use client";
import Link from "next/link";
import { useApp } from "@/lib/context";
import { euro } from "@/lib/money";
import type { Card } from "@/lib/server";

const EMOJI = ["🥛", "🥟", "🐟", "🍞", "🌾", "🍬", "🍵", "🥒", "🧀", "🥩", "🍯", "🥔"];
export function emojiFor(key: string): string {
  let h = 0;
  for (const c of key) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return EMOJI[h % EMOJI.length];
}

export function Photo({ image, name, className = "", size = "text-5xl" }: { image?: string | null; name: string; className?: string; size?: string }) {
  return (
    <div className={`ph relative flex items-center justify-center overflow-hidden rounded-image ${className}`} aria-hidden={!image}>
      {image ? <img src={`/media/${image}`} alt={name} className="h-full w-full object-cover" /> : <span className={size}>{emojiFor(name)}</span>}
    </div>
  );
}

export function Heart({ sku }: { sku: string }) {
  const { favs, toggleFav, t } = useApp();
  const on = favs.has(sku);
  return (
    <button type="button" aria-pressed={on} aria-label={on ? t.card.unfav : t.card.fav} onClick={(e) => { e.preventDefault(); void toggleFav(sku); }}
      className="flex h-10 w-10 items-center justify-center rounded-full bg-card/90 text-xl shadow-sm">
      <span className={on ? "text-terra" : "text-muted"}>{on ? "♥" : "♡"}</span>
    </button>
  );
}

export function StockBadge({ status }: { status: string }) {
  const { t } = useApp();
  if (status === "out_of_stock") return <span className="chip-terra">{t.card.outOfStock}</span>;
  if (status === "low_stock") return <span className="chip-terra">{t.card.lowStock}</span>;
  return null;
}

export function Qty({ value, max, onChange, small = false }: { value: number; max: number; onChange: (n: number) => void; small?: boolean }) {
  const s = small ? "h-9 w-9" : "h-11 w-11";
  return (
    <div className="inline-flex items-center gap-1 rounded-full border border-form-line bg-card">
      <button type="button" className={`${s} rounded-full text-xl font-black`} aria-label="−" onClick={() => onChange(value - 1)}>−</button>
      <span className="min-w-8 text-center font-extrabold" aria-live="polite">{value}</span>
      <button type="button" className={`${s} rounded-full text-xl font-black disabled:opacity-30`} aria-label="+" disabled={value >= max} onClick={() => onChange(value + 1)}>+</button>
    </div>
  );
}

export function PriceBlock({ p, large = false }: { p: Pick<Card, "price_cents" | "regular_cents" | "is_discounted" | "unit_price_cents" | "unit_price_per">; large?: boolean }) {
  const { lang, t } = useApp();
  return (
    <div>
      <div className="flex items-baseline gap-2">
        <span className={`${large ? "text-3xl" : "text-lg"} font-black ${p.is_discounted ? "text-terra" : ""}`}>{euro(p.price_cents, lang)}</span>
        {p.is_discounted && p.regular_cents ? <span className="text-sm text-muted line-through">{euro(p.regular_cents, lang)}</span> : null}
      </div>
      {p.unit_price_cents ? <div className="text-xs text-muted">{euro(p.unit_price_cents, lang)} {p.unit_price_per === "l" ? t.card.perL : t.card.perKg}</div> : null}
    </div>
  );
}

export function ProductCard({ p }: { p: Card }) {
  const { lang, t, cart, addToCart, setQty, removeLine, cartBusy } = useApp();
  const line = cart?.lines.find((l) => l.sku === p.sku);
  const out = p.stock_status === "out_of_stock";
  return (
    <article className="card flex flex-col overflow-hidden p-3">
      <Link href={`/${lang}/p/${p.slug}`} className="block">
        <div className="relative">
          <Photo image={p.image} name={p.name} className="aspect-square w-full" />
          <div className="absolute left-2 top-2 flex flex-wrap gap-1">
            {p.is_discounted ? <span className="chip-terra">{t.card.offer}</span> : null}
            {p.tags.includes("bestseller") && !p.is_discounted ? <span className="chip">{t.card.bestseller}</span> : null}
            {p.tags.includes("new") && !p.is_discounted ? <span className="chip">{t.card.new}</span> : null}
          </div>
          <div className="absolute right-2 top-2"><Heart sku={p.sku} /></div>
        </div>
        <h3 className="mt-3 line-clamp-2 min-h-[3rem] font-extrabold leading-snug">{p.name}</h3>
        <div className="text-sm text-muted">{[p.brand, p.unit_label].filter(Boolean).join(" · ") || " "}</div>
      </Link>
      <div className="mt-2 flex items-end justify-between gap-2">
        <PriceBlock p={p} />
        <StockBadge status={p.stock_status} />
      </div>
      <div className="mt-3">
        {out ? (
          <Link href={`/${lang}/p/${p.slug}#notify`} className="btn-outline btn-sm w-full">{t.card.notify}</Link>
        ) : line ? (
          <div className="flex justify-center">
            <Qty small value={line.qty} max={line.max_qty} onChange={(n) => (n <= 0 ? removeLine(p.sku) : setQty(p.sku, n))} />
          </div>
        ) : (
          <button type="button" className="btn btn-sm w-full" disabled={cartBusy} onClick={() => void addToCart(p.sku)}>{t.card.add}</button>
        )}
      </div>
    </article>
  );
}

export function Stepper({ step }: { step: 1 | 2 | 3 }) {
  const { t } = useApp();
  const items = [t.cartPage.title, t.checkout.title, t.order.weHave];
  return (
    <ol className="mb-6 flex items-center gap-3 text-sm font-bold">
      {items.map((label, i) => (
        <li key={label} className="flex items-center gap-2">
          <span className={`flex h-7 w-7 items-center justify-center rounded-full ${i + 1 <= step ? "bg-green text-white" : "bg-green-tint"}`}>{i + 1}</span>
          <span className={i + 1 === step ? "" : "text-muted"}>{label}</span>
          {i < 2 ? <span className="mx-1 h-px w-6 bg-line" /> : null}
        </li>
      ))}
    </ol>
  );
}

export function Toasts() {
  const { toasts } = useApp();
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex flex-col items-center gap-2" role="status" aria-live="polite">
      {toasts.map((x) => (
        <div key={x.id} className={`rounded-full px-5 py-3 text-sm font-bold text-white shadow-lg ${x.kind === "err" ? "bg-terra" : "bg-green"}`}>{x.text}</div>
      ))}
    </div>
  );
}

export function Crumbs({ items }: { items: { href?: string; label: string }[] }) {
  return (
    <nav aria-label="breadcrumb" className="mb-4 flex flex-wrap items-center gap-1 text-sm text-muted">
      {items.map((it, i) => (
        <span key={i} className="flex items-center gap-1">
          {it.href ? <Link href={it.href} className="hover:underline">{it.label}</Link> : <span className="font-bold text-green">{it.label}</span>}
          {i < items.length - 1 ? <span>›</span> : null}
        </span>
      ))}
    </nav>
  );
}
