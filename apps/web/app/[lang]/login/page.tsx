"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useApp } from "@/lib/context";

export default function Login() {
  const { lang, t, login } = useApp();
  const router = useRouter();
  const next = useSearchParams().get("next");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [forgot, setForgot] = useState(false);
  return (
    <div className="mx-auto max-w-md">
      <div className="card p-8">
        <h1 className="mb-4 text-3xl">{t.auth.loginTitle}</h1>
        <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); const code = await login(email, pw); if (code) setErr(t.auth.bad); else router.push(`/${lang}/${next ?? "account"}`); }}>
          <div><label className="label" htmlFor="email">{t.auth.email}</label><input id="email" type="email" className="field" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
          <div><label className="label" htmlFor="pw">{t.auth.password}</label><input id="pw" type="password" className="field" required autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} /></div>
          {err && <p className="err" role="alert">{err}</p>}
          <button className="btn w-full">{t.auth.loginBtn}</button>
          <button type="button" className="link text-sm" onClick={() => setForgot(true)}>{t.auth.forgot}</button>
          {forgot && <p className="text-sm text-muted">{t.auth.forgotInfo}</p>}
        </form>
        <div className="my-4 flex items-center gap-3 text-sm text-muted"><span className="h-px flex-1 bg-line" />·<span className="h-px flex-1 bg-line" /></div>
        <div className="space-y-2">
          <button className="btn-outline w-full" disabled title={t.auth.soon}>{t.auth.google} ({t.auth.soon})</button>
          <button className="btn-outline w-full" disabled title={t.auth.soon}>{t.auth.apple} ({t.auth.soon})</button>
        </div>
        <p className="mt-4 text-center text-sm"><Link href={`/${lang}/register`} className="link">{t.auth.registerTitle}</Link> · <Link href={`/${lang}/checkout`} className="link">{t.auth.guest}</Link></p>
      </div>
    </div>
  );
}
