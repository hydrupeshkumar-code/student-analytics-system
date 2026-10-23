// Screenshot the real SAAP app (local demo data) for scene planning.
import { chromium } from "playwright";

const OUT = new URL("./shots/", import.meta.url).pathname;
const BASE = "http://localhost:5173";
const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });

async function session(email, password, pages) {
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2, colorScheme: "light" });
  const page = await ctx.newPage();
  await page.goto(BASE + "/");
  await page.screenshot({ path: OUT + "login.png" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.keyboard.press("Enter");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(800);
  for (const [name, path] of pages) {
    await page.goto(BASE + path);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1200);
    await page.screenshot({ path: OUT + name + ".png" });
    await page.screenshot({ path: OUT + name + "-full.png", fullPage: true });
  }
  await ctx.close();
}

await session("neha@saap.edu", "Faculty@123", [
  ["fac-dash", "/"],
  ["c1-overview", "/courses/1"],
  ["c1-gradebook", "/courses/1/gradebook"],
  ["c1-attainment", "/courses/1/attainment"],
  ["c1-outcomes", "/courses/1/outcomes"],
  ["c2-overview", "/courses/2"],
  ["c2-risk", "/courses/2/risk"],
  ["c2-assessments", "/courses/2/assessments"],
  ["c2-marks", "/courses/2/marks"],
  ["rubrics", "/rubrics"],
]);
await session("student@saap.edu", "Student@123", [
  ["stu-dash", "/"],
  ["stu-c1", "/my/courses/1"],
]);
await session("admin@saap.edu", "Admin@123", [
  ["adm-dash", "/"],
  ["adm-attain", "/attainment"],
  ["adm-ml", "/ml"],
]);
await browser.close();
