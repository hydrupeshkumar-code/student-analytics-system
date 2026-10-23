// Grab real markup (illustration SVG) and element crops for the composition.
import { chromium } from "playwright";
import fs from "node:fs";

const OUT = new URL("./shots/", import.meta.url).pathname;
const BASE = "http://localhost:5173";
const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
const settle = async (ms = 900) => { await page.waitForLoadState("networkidle"); await page.waitForTimeout(ms); };

await page.goto(BASE + "/");
await settle();
fs.writeFileSync(OUT + "illus.svg", await page.locator(".login-hero svg.illus").evaluate((el) => el.outerHTML));
await page.fill('input[type="email"]', "neha@saap.edu");
await page.fill('input[type="password"]', "Faculty@123");
await page.keyboard.press("Enter");
await settle();

await page.goto(BASE + "/courses/1/attainment");
await settle();
const cards = page.locator(".card");
const n = await cards.count();
for (let i = 0; i < Math.min(n, 3); i++) await cards.nth(i).screenshot({ path: OUT + `attain-card-${i}.png` });
const btn = page.getByRole("button", { name: /PDF for NAAC/ });
const c0 = await cards.nth(0).boundingBox();
const b = await btn.boundingBox();
fs.writeFileSync(OUT + "attain-card-0.json", JSON.stringify({ card: c0, btn: b }));

await page.goto(BASE + "/courses/2/risk");
await settle();
const stats = page.locator(".stat, .kpi, .card").first();
await page.locator("main").screenshot({ path: OUT + "risk-main.png" });
console.log("cards on attainment", n);
await browser.close();
