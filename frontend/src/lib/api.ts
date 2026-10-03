const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";
const ACCESS = "saap.access";
const REFRESH = "saap.refresh";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function read(key: string) {
  try { return localStorage.getItem(key); } catch { return null; }
}

export const tokens = {
  get access() { return read(ACCESS); },
  get refresh() { return read(REFRESH); },
  set(access: string, refresh: string) {
    try { localStorage.setItem(ACCESS, access); localStorage.setItem(REFRESH, refresh); } catch { /* private mode */ }
  },
  clear() {
    try { localStorage.removeItem(ACCESS); localStorage.removeItem(REFRESH); } catch { /* ignore */ }
  },
};

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

let refreshing: Promise<boolean> | null = null;
async function tryRefresh(): Promise<boolean> {
  const rt = tokens.refresh;
  if (!rt) return false;
  refreshing ??= (async () => {
    try {
      const r = await fetch(`${BASE}/auth/refresh`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: rt }),
      });
      if (!r.ok) return false;
      const data = await r.json();
      tokens.set(data.access_token, data.refresh_token);
      return true;
    } catch { return false; } finally { setTimeout(() => { refreshing = null; }, 0); }
  })();
  return refreshing;
}

function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return d.map((e) => {
        const loc = Array.isArray(e.loc) ? e.loc.filter((x: unknown) => x !== "body").join(" → ") : "";
        return `${loc ? loc + ": " : ""}${String(e.msg).replace(/^Value error, /, "")}`;
      }).join("; ");
    }
  }
  return status >= 500 ? "Server error — please try again" : `Request failed (${status})`;
}

async function raw(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  const t = tokens.access;
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  let r: Response;
  try {
    r = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check your connection.");
  }
  if (r.status === 401 && retry && !path.startsWith("/auth/login")) {
    if (await tryRefresh()) return raw(path, init, false);
    tokens.clear();
    onUnauthorized();
  }
  if (!r.ok) {
    let body: unknown = null;
    try { body = await r.json(); } catch { /* not json */ }
    throw new ApiError(r.status, errorMessage(body, r.status));
  }
  return r;
}

export async function api<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const r = await raw(path, init);
  if (r.status === 204) return undefined as T;
  return r.json() as Promise<T>;
}

export const get = <T,>(p: string) => api<T>(p);
export const post = <T,>(p: string, body?: unknown) => api<T>(p, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
export const put = <T,>(p: string, body: unknown) => api<T>(p, { method: "PUT", body: JSON.stringify(body) });
export const patch = <T,>(p: string, body: unknown) => api<T>(p, { method: "PATCH", body: JSON.stringify(body) });
export const del = <T,>(p: string) => api<T>(p, { method: "DELETE" });

export async function upload<T>(p: string, file: File): Promise<T> {
  const fd = new FormData();
  fd.append("file", file);
  return api<T>(p, { method: "POST", body: fd });
}

/** Download an authenticated file (PDF/XLSX/CSV) and save it with the server-provided name. */
export async function download(p: string, fallbackName = "download") {
  const r = await raw(p);
  const blob = await r.blob();
  const cd = r.headers.get("Content-Disposition") ?? "";
  const name = /filename="?([^";]+)"?/.exec(cd)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
