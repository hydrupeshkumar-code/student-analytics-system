// Capture interaction states of the real app: rubric scoring, risk rows, attainment export.
import { chromium } from "playwright";
import fs from "node:fs";

const OUT = new URL("./shots/", import.meta.url).pathname;
const BASE = "http://localhost:5173";
const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2, acceptDownloads: true });
const page = await ctx.newPage();
const settle = async (ms = 700) => { await page.waitForLoadState("networkidle"); await page.waitForTimeout(ms); };

await page.goto(BASE + "/");
await page.fill('input[type="email"]', "neha@saap.edu");
await page.fill('input[type="password"]', "Faculty@123");
await page.keyboard.press("Enter");
await settle();

// --- Rubric scoring on CS301 Lab evaluation
await page.goto(BASE + "/courses/2/marks");
await settle();
await page.getByText("Enter marks").first().click();
await settle();
await page.screenshot({ path: OUT + "marks-grid.png" });
await page.getByRole("button", { name: "Score", exact: true }).first().click();
await page.waitForTimeout(600);
const modal = page.locator(".modal, [role=dialog]").first();
await modal.screenshot({ path: OUT + "rubric-0.png" });
await page.screenshot({ path: OUT + "rubric-page-0.png" });
const rows = await page.locator(".rubric-grid").evaluate((g) => {
  // cells laid out row-major: criterion label + one cell per level
  return g.querySelectorAll(".rubric-cell").length;
});
console.log("rubric cells", rows);
const picks = [0, 1, 0, 1]; // level index per criterion (0 = top level)
const levels = rows / picks.length;
for (let c = 0; c < picks.length; c++) {
  const cell = page.locator(".rubric-grid .rubric-cell").nth(c * levels + picks[c]);
  const box = await cell.boundingBox();
  const mbox = await modal.boundingBox();
  fs.writeFileSync(OUT + `rubric-${c + 1}.json`, JSON.stringify({ cell: box, modal: mbox }));
  await cell.click();
  await page.waitForTimeout(400);
  await modal.screenshot({ path: OUT + `rubric-${c + 1}.png` });
}

// --- Early-warning rows on CS301
await page.goto(BASE + "/courses/2/risk");
await settle(1000);
await page.locator("table").first().screenshot({ path: OUT + "risk-table.png" });
const trs = page.locator("table tbody tr");
for (let i = 0; i < 5; i++) await trs.nth(i).screenshot({ path: OUT + `risk-row-${i}.png` });
await page.locator("table thead").first().screenshot({ path: OUT + "risk-head.png" });
const cards = page.locator(".stat, .card").filter({ hasText: /High risk|Medium risk|Low risk|Model/ });
console.log("risk cards", await cards.count());

// --- Attainment on CS204 + real PDF
await page.goto(BASE + "/courses/1/attainment");
await settle(1000);
const pdfBtn = page.getByRole("button", { name: /PDF for NAAC/ });
fs.writeFileSync(OUT + "attain-btn.json", JSON.stringify(await pdfBtn.boundingBox()));
const [dl] = await Promise.all([page.waitForEvent("download"), pdfBtn.click()]);
await dl.saveAs(OUT + "attainment.pdf");
await page.screenshot({ path: OUT + "attain-page.png" });

await browser.close();
