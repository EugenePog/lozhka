import Link from "next/link";
import { messages } from "@/lib/messages";
import type { Lang } from "@/lib/i18n";

export function Footer({ lang }: { lang: Lang }) {
  const t = messages[lang];
  return (
    <footer className="mt-16 bg-green text-white">
      <div className="container-page grid gap-8 py-10 sm:grid-cols-3">
        <div>
          <div className="text-2xl font-black">🥄 Lozhka</div>
          <p className="mt-2 text-sm opacity-80">{t.footer.tagline}</p>
        </div>
        <div>
          <h4 className="mb-2 font-extrabold">{t.footer.help}</h4>
          <ul className="space-y-1 text-sm opacity-90">
            <li><Link href={`/${lang}/help/delivery`}>{t.footer.delivery}</Link></li>
            <li><Link href={`/${lang}/help/about`}>{t.footer.about}</Link></li>
          </ul>
        </div>
        <div>
          <h4 className="mb-2 font-extrabold">{t.footer.company}</h4>
          <ul className="space-y-1 text-sm opacity-90">
            <li><Link href={`/${lang}/help/terms`}>{t.footer.terms}</Link></li>
            <li><Link href={`/${lang}/help/privacy`}>{t.footer.privacy}</Link></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/20 py-3 text-center text-xs opacity-70">{t.footer.legal}</div>
    </footer>
  );
}
