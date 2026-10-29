"use client";
import { useState } from "react";
import { useApp } from "@/lib/context";
import { api } from "@/lib/api";

export function Newsletter() {
  const { t, lang } = useApp();
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);
  return (
    <section className="mt-12 rounded-card bg-green p-8 text-white">
      <h2>{t.home.newsletter}</h2>
      <p className="opacity-80">{t.home.newsletterD}</p>
      {done ? <p className="mt-4 font-bold">{t.home.subscribed}</p> : (
        <form className="mt-4 flex max-w-md gap-2" onSubmit={async (e) => { e.preventDefault(); await api.POST("/api/v1/newsletter", { body: { email, lang } }); setDone(true); }}>
          <input type="email" required className="field text-green" placeholder={t.home.email} value={email} onChange={(e) => setEmail(e.target.value)} />
          <button className="btn">{t.home.subscribe}</button>
        </form>
      )}
    </section>
  );
}
