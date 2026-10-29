"use client";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { messages } from "@/lib/messages";
import { isLang, DEFAULT_LANG } from "@/lib/i18n";

/** Stand-in for the PSP's hosted page (iDEAL / card). Replaced by the real provider redirect later. */
export default function TestPay() {
  const { number } = useParams<{ number: string }>();
  const token = useSearchParams().get("token") ?? "";
  const router = useRouter();
  const cookie = typeof document !== "undefined" ? document.cookie.match(/lozhka_lang=(\w+)/)?.[1] : undefined;
  const lang = cookie && isLang(cookie) ? cookie : DEFAULT_LANG;
  const t = messages[lang];
  const done = async (result: "success" | "fail") => {
    await api.POST("/api/v1/payments/test/{number}/complete", { params: { path: { number } }, body: { token, result } });
    router.push(result === "success" ? `/${lang}/order/${number}?token=${token}` : `/${lang}/checkout`);
  };
  return (
    <main className="mx-auto mt-20 max-w-md px-4">
      <div className="card p-8 text-center">
        <div className="text-5xl">💳</div>
        <h1 className="mt-2 text-3xl">{t.pay.title}</h1>
        <p className="mt-2 text-muted">{t.pay.intro}</p>
        <p className="mt-2 font-bold">{number}</p>
        <button className="btn mt-6 w-full" onClick={() => done("success")}>{t.pay.success}</button>
        <button className="btn-outline mt-3 w-full" onClick={() => done("fail")}>{t.pay.fail}</button>
      </div>
    </main>
  );
}
