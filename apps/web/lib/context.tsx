"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, problemOf, resetCsrf } from "./api";
import { fmt, messages, type Messages } from "./messages";
import type { Lang } from "./i18n";
import type { Cart } from "./server";
import type { Schemas } from "@lozhka/api-client";

type Me = Schemas["MeOut"];
type Toast = { id: number; text: string; kind?: "ok" | "err" };

type Ctx = {
  lang: Lang; t: Messages; tf: typeof fmt;
  cart: Cart | null; cartBusy: boolean;
  addToCart: (sku: string, qty?: number) => Promise<boolean>;
  setQty: (sku: string, qty: number) => Promise<void>;
  removeLine: (sku: string) => Promise<void>;
  applyPromo: (code: string) => Promise<void>;
  refreshCart: () => Promise<void>;
  me: Me | null; meLoaded: boolean;
  refreshMe: () => Promise<void>;
  login: (email: string, password: string) => Promise<string | null>;
  register: (body: Schemas["RegisterIn"]) => Promise<string | null>;
  logout: () => Promise<void>;
  favs: Set<string>; toggleFav: (sku: string) => Promise<void>;
  toast: (text: string, kind?: "ok" | "err") => void; toasts: Toast[];
  minOrder: number;
};

const C = createContext<Ctx>(null as unknown as Ctx);
export const useApp = () => useContext(C);

export function AppProvider({ lang, minOrder, children }: { lang: Lang; minOrder: number; children: React.ReactNode }) {
  const [cart, setCart] = useState<Cart | null>(null);
  const [cartBusy, setBusy] = useState(false);
  const [me, setMe] = useState<Me | null>(null);
  const [meLoaded, setMeLoaded] = useState(false);
  const [favs, setFavs] = useState<Set<string>>(new Set());
  const [toasts, setToasts] = useState<Toast[]>([]);
  const t = messages[lang];

  const toast = useCallback((text: string, kind: "ok" | "err" = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((x) => [...x, { id, text, kind }]);
    setTimeout(() => setToasts((x) => x.filter((i) => i.id !== id)), 3500);
  }, []);

  const refreshCart = useCallback(async () => {
    const { data } = await api.GET("/api/v1/cart", { params: { query: { lang } } });
    if (data) setCart(data);
  }, [lang]);

  const loadFavs = useCallback(async () => {
    const { data } = await api.GET("/api/v1/me/favourites");
    setFavs(new Set(data ?? []));
  }, []);

  const refreshMe = useCallback(async () => {
    const { data } = await api.GET("/api/v1/auth/me");
    setMe(data ?? null);
    setMeLoaded(true);
    if (data) await loadFavs(); else setFavs(new Set());
  }, [loadFavs]);

  useEffect(() => { void refreshCart(); void refreshMe(); }, [refreshCart, refreshMe]);

  const wrap = async (fn: () => Promise<{ data?: Cart; error?: unknown }>): Promise<boolean> => {
    setBusy(true);
    try {
      const { data, error } = await fn();
      if (data) { setCart(data); return true; }
      if (error) toast(problemOf(error).detail || t.common.error, "err");
      return false;
    } finally { setBusy(false); }
  };

  const value = useMemo<Ctx>(() => ({
    lang, t, tf: fmt, cart, cartBusy, me, meLoaded, favs, toasts, minOrder, toast, refreshCart, refreshMe,
    addToCart: async (sku, qty = 1) => {
      const ok = await wrap(() => api.POST("/api/v1/cart/items", { params: { query: { lang } }, body: { sku, qty } }) as never);
      if (ok) toast(t.card.added);
      return ok;
    },
    setQty: async (sku, qty) => { await wrap(() => api.PUT("/api/v1/cart/items/{sku}", { params: { path: { sku }, query: { lang } }, body: { qty } }) as never); },
    removeLine: async (sku) => { await wrap(() => api.DELETE("/api/v1/cart/items/{sku}", { params: { path: { sku }, query: { lang } } }) as never); },
    applyPromo: async (code) => { await wrap(() => api.POST("/api/v1/cart/promo", { params: { query: { lang } }, body: { code } }) as never); },
    login: async (email, password) => {
      const { error } = await api.POST("/api/v1/auth/login", { body: { email, password } });
      if (error) return problemOf(error).code;
      resetCsrf(); await refreshMe(); await refreshCart(); return null;
    },
    register: async (body) => {
      const { error } = await api.POST("/api/v1/auth/register", { body });
      if (error) return problemOf(error).code;
      resetCsrf(); await refreshMe(); await refreshCart(); return null;
    },
    logout: async () => {
      await api.POST("/api/v1/auth/logout");
      resetCsrf(); setMe(null); setFavs(new Set()); await refreshCart();
    },
    toggleFav: async (sku) => {
      if (!me) { toast(t.card.loginFirst, "err"); return; }
      const on = favs.has(sku);
      setFavs((s) => { const n = new Set(s); if (on) n.delete(sku); else n.add(sku); return n; });
      if (on) await api.DELETE("/api/v1/me/favourites/{sku}", { params: { path: { sku } } });
      else await api.PUT("/api/v1/me/favourites/{sku}", { params: { path: { sku } } });
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [lang, t, cart, cartBusy, me, meLoaded, favs, toasts, minOrder, toast, refreshCart, refreshMe]);

  return <C.Provider value={value}>{children}</C.Provider>;
}
