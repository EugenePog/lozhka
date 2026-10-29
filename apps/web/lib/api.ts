"use client";
import { createApi, problemOf, resetCsrf } from "@lozhka/api-client";

/** Same-origin: Next rewrites /api to the Django API, so session and CSRF cookies just work. */
export const api = createApi("");
export { problemOf, resetCsrf };
