import type { Schemas } from "@lozhka/api-client";
import type { Lang } from "./i18n";

const API = process.env.API_URL ?? "http://localhost:8010";

/** Server-side GET against the public API (no cookies: public catalogue data only). */
export async function sget<T>(path: string, revalidate = 0): Promise<T | null> {
  try {
    const res = await fetch(`${API}/api/v1${path}`, revalidate ? { next: { revalidate } } : { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export type Card = Schemas["ProductCard"];
export type Detail = Schemas["ProductDetail"];
export type Category = Schemas["CategoryOut"];
export type Cart = Schemas["CartOut"];
export type Slot = Schemas["SlotOut"];
export type Offers = Schemas["DeliveryOffersOut"];
export type Order = Schemas["OrderOut"];
export type Content = Schemas["ContentOut"];
export const q = (lang: Lang) => `lang=${lang}`;
