// The only place that calls fetch. Every response that is not 2xx becomes an ApiError with the
// backend's {"error": {code, message, details}} body, so pages can show `err.message` directly.
const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "") + "/api/v1";
const TOKEN_KEY = "advisor.token";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) {
    super(message);
  }
}

export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(t: string | null) {
    try {
      if (t) localStorage.setItem(TOKEN_KEY, t);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* private mode: the session simply won't survive a reload */
    }
  },
};

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

type Query = Record<string, string | number | boolean | null | undefined>;

export async function request<T>(method: string, path: string, opts: { body?: unknown; query?: Query } = {}): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(opts.query ?? {})) if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  const url = BASE + path + (qs.size ? "?" + qs : "");
  const headers: Record<string, string> = {};
  const token = tokenStore.get();
  if (token) headers.Authorization = "Bearer " + token;
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(url, { method, headers, body: opts.body === undefined ? undefined : JSON.stringify(opts.body) });
  } catch {
    throw new ApiError(0, "network_error", "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ กรุณาตรวจสอบอินเทอร์เน็ตแล้วลองใหม่");
  }
  if (res.status === 204) return undefined as T;
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const e = data?.error;
    if (res.status === 401 && token && path !== "/auth/login") onUnauthorized();
    throw new ApiError(res.status, e?.code ?? "error", e?.message ?? `เกิดข้อผิดพลาด (${res.status})`, e?.details);
  }
  return data as T;
}

export const get = <T>(path: string, query?: Query) => request<T>("GET", path, { query });
export const post = <T>(path: string, body?: unknown) => request<T>("POST", path, { body: body ?? {} });
export const patch = <T>(path: string, body: unknown) => request<T>("PATCH", path, { body });
export const put = <T>(path: string, body: unknown) => request<T>("PUT", path, { body });

/** Authenticated file download (the Authorization header can't be sent by a plain <a href>). */
export async function download(path: string, filename: string): Promise<void> {
  const token = tokenStore.get();
  let res: Response;
  try {
    res = await fetch(BASE + path, { headers: token ? { Authorization: "Bearer " + token } : {} });
  } catch {
    throw new ApiError(0, "network_error", "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ กรุณาตรวจสอบอินเทอร์เน็ตแล้วลองใหม่");
  }
  if (!res.ok) throw new ApiError(res.status, "error", `ดาวน์โหลดไม่สำเร็จ (${res.status})`);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
