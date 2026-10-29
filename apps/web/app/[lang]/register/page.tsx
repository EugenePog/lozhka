"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useApp } from "@/lib/context";

export default function Register() {
  const { lang, t, register } = useApp();
  const router = useRouter();
  const [f, setF] = useState({ name: "", email: "", password: "" });
  const [marketing, setMarketing] = useState(false);
  const [err, setErr] = useState("");
  const strength = f.password.length >= 12 ? 3 : f.password.length >= 8 ? 2 : f.password ? 1 : 0;
  const labels = ["", t.auth.weak, t.auth.ok, t.auth.strong];
  return (
    <div className="mx-auto max-w-md">
      <div className="card p-8">
        <h1 className="mb-4 text-3xl">{t.auth.registerTitle}</h1>
        <form className="space-y-3" onSubmit={async (e) => {
          e.preventDefault();
          if (f.password.length < 8) { setErr(t.auth.shortPw); return; }
          const [first, ...rest] = f.name.trim().split(/\s+/);
          const code = await register({ email: f.email, password: f.password, first_name: first ?? "", last_name: rest.join(" "), phone: "", language: lang, marketing_opt_in: marketing });
          if (code) setErr(code === "email_taken" ? t.auth.taken : t.common.error); else router.push(`/${lang}/account`);
        }}>
          <div><label className="label" htmlFor="name">{t.auth.name}</label><input id="name" className="field" required autoComplete="name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
          <div><label className="label" htmlFor="email">{t.auth.email}</label><input id="email" type="email" className="field" required autoComplete="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></div>
          <div>
            <label className="label" htmlFor="pw">{t.auth.password}</label>
            <input id="pw" type="password" className="field" required autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
            <div className="mt-1 flex items-center gap-2"><div className="h-1.5 flex-1 overflow-hidden rounded-full bg-green-tint"><div className={`h-full ${strength === 1 ? "bg-terra" : "bg-green"}`} style={{ width: `${strength * 33.3}%` }} /></div><span className="text-xs">{labels[strength]}</span></div>
          </div>
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={marketing} onChange={(e) => setMarketing(e.target.checked)} /> {t.auth.marketing}</label>
          {err && <p className="err" role="alert">{err}</p>}
          <button className="btn w-full">{t.auth.create}</button>
          <p className="text-xs text-muted">{t.auth.terms}</p>
        </form>
        <p className="mt-4 text-center text-sm"><Link href={`/${lang}/login`} className="link">{t.auth.loginTitle}</Link></p>
      </div>
    </div>
  );
}
