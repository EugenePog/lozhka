import { notFound } from "next/navigation";
import { isLang } from "@/lib/i18n";
import { messages, fmt } from "@/lib/messages";
import { sget, type Content, type Offers } from "@/lib/server";
import { euro } from "@/lib/money";

const SLUGS = ["delivery", "about", "terms", "privacy"];

export default async function Help({ params }: { params: Promise<{ lang: string; slug: string }> }) {
  const { lang, slug } = await params;
  if (!isLang(lang) || !SLUGS.includes(slug)) notFound();
  const t = messages[lang];
  const [page, offers, settings] = await Promise.all([
    sget<Content>(`/pages/page-${slug}?lang=${lang}`),
    slug === "delivery" ? sget<Offers>("/delivery/offers?postcode=1012AB") : Promise.resolve(null),
    sget<Record<string, unknown>>("/settings"),
  ]);
  if (!page) notFound();
  const min = Number(settings?.min_order_cents ?? 5000);
  return (
    <article className="mx-auto max-w-3xl">
      <h1 className="mb-4">{page.title}</h1>
      <div className="card space-y-3 whitespace-pre-line p-6">{page.body_markdown}</div>
      {slug === "delivery" && (
        <>
          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            {[[t.help.cards.c1, t.help.cards.c1d], [t.help.cards.c2, t.help.cards.c2d], [t.help.cards.c3, fmt(t.help.cards.c3d, { min: (min / 100).toFixed(0) })]].map(([a, b]) => (
              <div key={a} className="card p-4"><div className="font-extrabold">{a}</div><div className="text-sm text-muted">{b}</div></div>
            ))}
          </div>
          {offers && offers.fee_tiers.length > 0 && (
            <table className="card mt-6 w-full text-left">
              <caption className="mb-2 text-left text-xl font-black">{t.help.fees}</caption>
              <thead><tr className="text-sm text-muted"><th className="p-3">{t.help.orderValue}</th><th className="p-3">{t.help.fee}</th></tr></thead>
              <tbody>
                {offers.fee_tiers.map((x) => (
                  <tr key={x.min_subtotal_cents} className="border-t border-line">
                    <td className="p-3">{euro(x.min_subtotal_cents, lang)}{x.max_subtotal_cents ? ` – ${euro(x.max_subtotal_cents, lang)}` : "+"}</td>
                    <td className="p-3 font-bold">{x.fee_cents ? euro(x.fee_cents, lang) : t.checkout.free}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </article>
  );
}
