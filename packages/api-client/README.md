# api-client

Typed TypeScript client for the public API (`services/api`), used by `apps/web` and later the mobile app.

- `openapi.json` is exported from the Django project: `pnpm --filter @lozhka/api-client export`
- `src/schema.d.ts` is generated from it: `pnpm --filter @lozhka/api-client generate` (or both: `refresh`). **Never edit generated files by hand.**
- `src/index.ts` is the small hand-written wrapper (CSRF header for changing calls, error shape).

Re-run `refresh` whenever an endpoint or schema changes; CI fails if `schema.d.ts` is out of date.
