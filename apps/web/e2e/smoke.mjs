// End-to-end smoke test of the customer site: browse, search, cart, checkout (pay on delivery), order page, login, account.
// Needs the API on :8010 and the web app on :3010 with the demo seed loaded.  Run: node e2e/smoke.mjs [outDir]
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const BASE = process.env.WEB_URL ?? "http://localhost:3010";
const OUT = process.argv[2] ?? "e2e/out";
import fs from "node:fs";
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "en-GB" });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource|hydrat/.test(m.text())) errors.push(`console: ${m.text()}`); });
const step = (s) => console.log("•", s);
const shot = (n) => page.screenshot({ path: `${OUT}/${n}.png`, fullPage: true });
const ok = (c, msg) => { if (!c) { errors.push(`ASSERT: ${msg}`); console.log("  ✗", msg); } };

step("home");
await page.goto(`${BASE}/en`);
await page.waitForSelector("article");
ok((await page.locator("article").count()) >= 5, "home shows products");
await shot("01-home");

step("category + filters");
await page.goto(`${BASE}/en/c/dairy-eggs`);
await page.waitForSelector("article");
await shot("02-category");

step("search (typo-tolerant substring)");
await page.goto(`${BASE}/en/search?q=kefir`);
await page.waitForSelector("article");
ok((await page.locator("article").count()) >= 1, "search finds kefir");

step("add to cart from card");
await page.getByRole("button", { name: "Add", exact: true }).first().click();
await page.waitForSelector('[data-testid="cart-count"]');
ok((await page.getByTestId("cart-count").innerText()) === "1", "cart badge = 1");

step("product page");
await page.locator("article a").first().click();
await page.waitForSelector("h1");
await shot("03-product");
for (let i = 0; i < 12; i++) { // fill the cart past the minimum order using real products
  const add = page.getByRole("button", { name: /add to cart|maximum available/i });
  if (await add.isDisabled()) break;
  await add.click(); await page.waitForTimeout(150);
}

step("cart");
await page.goto(`${BASE}/en/cart`);
await page.waitForSelector("[data-sku]");
await shot("04-cart");
// top up with a few different products until the minimum is reached
await page.goto(`${BASE}/en/c/all`);
await page.waitForSelector("article");
const adds = page.getByRole("button", { name: "Add", exact: true });
for (let i = 0; i < 22 && (await adds.count()); i++) { await adds.first().click(); await page.waitForTimeout(250); }
await page.goto(`${BASE}/en/cart`); await page.waitForSelector("[data-sku]");
ok((await page.getByText(/Minimum reached/).count()) === 1, "minimum order reached");

step("checkout (guest, pay on delivery)");
await page.getByRole("link", { name: /^checkout$/i }).click();
await page.waitForSelector("#email");
await page.fill("#email", "e2e@lozhka.example");
await page.fill("#phone", "0612345678");
await page.fill("#first_name", "Eva");
await page.fill("#last_name", "Test");
await page.fill("#street", "Damrak");
await page.fill("#house_number", "1");
await page.fill("#postcode", "1012 LG");
await page.fill("#city", "Amsterdam");
await page.waitForSelector('input[name="slot"]');
await shot("05-checkout");
await page.getByLabel(/I accept the terms/).check();
await page.getByRole("button", { name: /^place order$/i }).click();
await page.waitForURL(/\/order\/LZ-\d+/);
await page.waitForSelector("h1");
const order = page.url().match(/LZ-\d+/)[0];
ok(/Thank you/.test(await page.locator("h1").innerText()), "thank-you heading");
await shot("06-order");
console.log("  order", order);

step("login + account + reorder");
await page.goto(`${BASE}/en/login`);
await page.fill("#email", "demo@lozhka.example");
await page.fill("#pw", "demo1234");
await page.getByRole("button", { name: /^log in$/i }).click();
await page.waitForURL(/\/account/);
await page.waitForSelector("text=LZ-1000");
await shot("07-account");
await page.goto(`${BASE}/en/account?tab=addresses`);
await page.waitForSelector("text=Add address");
await page.goto(`${BASE}/en/account?tab=favourites`);
await page.waitForTimeout(500);

step("nl and ru render");
for (const l of ["nl", "ru"]) { await page.goto(`${BASE}/${l}`); await page.waitForSelector("article"); await shot(`08-home-${l}`); }

step("mobile");
await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${BASE}/en`); await page.waitForSelector("article");
await shot("09-home-mobile");
ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), "no horizontal scroll on mobile");

await browser.close();
console.log(errors.length ? `\nFAILED (${errors.length})\n${errors.join("\n")}` : "\nALL OK");
process.exit(errors.length ? 1 : 0);
