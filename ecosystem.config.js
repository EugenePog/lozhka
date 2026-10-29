// pm2 process definitions. Start with:  pm2 start ecosystem.config.js --only lozhka-worker
// Processes whose code does not exist yet are marked with their phase (docs 06_repo_deployment.md section 3).
// Enable them by removing the `disabled` flag as each phase lands.
try { process.loadEnvFile(".env"); } catch (e) { /* .env missing: rely on the real environment */ }

const env = process.env;
const venv = ".venv/bin";
const common = { autorestart: true, max_restarts: 10, min_uptime: "10s", time: true };

const dbUrl = (suffix) => env["LOZHKA_DATABASE_URL_" + suffix];

const apps = [
  { // Phase 2
    disabled: false,
    name: "lozhka-api",
    script: `${venv}/gunicorn`, interpreter: "none",
    args: "config.asgi:application -k uvicorn.workers.UvicornWorker -w 2 -b 127.0.0.1:8010",
    cwd: "services/api/src",
    env: { LOZHKA_DATABASE_URL: dbUrl("API"), DJANGO_SETTINGS_MODULE: "config.settings.public" },
  },
  { // Phase 1
    disabled: false,
    name: "lozhka-backoffice",
    script: `${venv}/gunicorn`, interpreter: "none",
    args: "config.asgi:application -k uvicorn.workers.UvicornWorker -w 1 -b 127.0.0.1:8011",
    cwd: "services/api/src",
    env: { LOZHKA_DATABASE_URL: dbUrl("BACKOFFICE"), DJANGO_SETTINGS_MODULE: "config.settings.backoffice" },
  },
  { // Phase 2
    disabled: false,
    name: "lozhka-web",
    script: "pnpm", args: "--filter @lozhka/web start", interpreter: "none",
    exec_mode: "fork",
    env: { NODE_ENV: "production", API_URL: "http://127.0.0.1:8010" },
  },
  { // Phase 1: queues default + pipelines
    disabled: true,
    name: "lozhka-worker",
    script: `${venv}/procrastinate`, interpreter: "none",
    args: "--app=lozhka_worker.app.app worker --queues default,pipelines",
    env: { LOZHKA_DATABASE_URL: dbUrl("PIPELINE") },
  },
  { // Phase 3: queue routing, concurrency 1
    disabled: true,
    name: "lozhka-worker-routing",
    script: `${venv}/procrastinate`, interpreter: "none",
    args: "--app=lozhka_worker.app.app worker --queues routing --concurrency 1",
    env: { LOZHKA_DATABASE_URL: dbUrl("PLANNER") },
  },
  { // Phase 4: the only process with the supplier-credential key
    disabled: true,
    name: "lozhka-worker-purchasing",
    script: `${venv}/procrastinate`, interpreter: "none",
    args: "--app=lozhka_worker.app.app worker --queues purchasing --concurrency 1",
    env: { LOZHKA_DATABASE_URL: dbUrl("PURCHASING"), SUPPLIER_SECRET_KEYS: env.SUPPLIER_SECRET_KEYS },
  },
];

module.exports = {
  apps: apps.filter((a) => !a.disabled).map(({ disabled, ...rest }) => ({ ...common, ...rest })),
};
