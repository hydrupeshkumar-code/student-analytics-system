// Deterministic frame renderer: each frame = render(t) of comp/index.html.
// Usage: node render.mjs stills 1.5 4.2 ...   |   node render.mjs video out.mp4
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import fs from "node:fs";

const FPS = 30, DURATION = 21.5;
const URL_ = "http://127.0.0.1:8765/brag-output/work/comp/index.html";
const [mode, ...args] = process.argv.slice(2);
const dir = new URL(".", import.meta.url).pathname;

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1, colorScheme: "light" });
page.on("console", (m) => m.type() === "error" && console.error("page:", m.text()));
page.on("pageerror", (e) => console.error("pageerror:", e.message));
await page.goto(URL_);
await page.evaluate(() => window.ready);

const frame = async (t) => {
  await page.evaluate((t) => window.render(t), t);
  return page.screenshot({ type: "jpeg", quality: 95 });
};

if (mode === "stills") {
  fs.mkdirSync(dir + "stills", { recursive: true });
  for (const a of args) fs.writeFileSync(dir + `stills/t${a}.jpg`, await frame(parseFloat(a)));
} else {
  const out = args[0] || dir + "video-only.mp4";
  const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "-",
    "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-r", String(FPS), out], { stdio: ["pipe", "inherit", "inherit"] });
  const N = Math.round(FPS * DURATION);
  for (let i = 0; i < N; i++) {
    const buf = await frame(i / FPS);
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
    if (i % 60 === 0) console.log(`frame ${i}/${N}`);
  }
  ff.stdin.end();
  await new Promise((r) => ff.on("close", r));
}
await browser.close();
