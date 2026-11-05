const TZ = "Asia/Bangkok";
const fmt = (o: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat("th-TH", { timeZone: TZ, ...o });

const fDay = fmt({ weekday: "long", day: "numeric", month: "long" });
const fShortDay = fmt({ weekday: "short", day: "numeric", month: "short" });
const fTime = fmt({ hour: "2-digit", minute: "2-digit", hour12: false });
const fDateTime = fmt({ day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false });
const fYmd = new Intl.DateTimeFormat("en-CA", { timeZone: TZ });

export const dayLabel = (iso: string) => fDay.format(new Date(iso));
export const shortDay = (iso: string) => fShortDay.format(new Date(iso));
export const timeLabel = (iso: string) => fTime.format(new Date(iso));
export const dateTime = (iso: string) => fDateTime.format(new Date(iso)) + " น.";
export const dayKey = (iso: string) => fYmd.format(new Date(iso)); // yyyy-mm-dd in Bangkok time
export const range = (a: string, b: string) => `${timeLabel(a)}–${timeLabel(b)} น.`;
export const dueLabel = (ymd: string | null) =>
  ymd ? new Intl.DateTimeFormat("th-TH", { timeZone: "UTC", day: "numeric", month: "short" }).format(new Date(ymd + "T00:00:00Z")) : "ไม่กำหนด";
export const pct = (v: number | null) => (v === null ? "–" : Math.round(v * 100) + "%");

/** "2030-01-31T09:00" from a <input type=datetime-local> -> ISO with the Bangkok offset the API requires. */
/** The reverse: an ISO instant -> "2030-01-31T09:00" in Bangkok time, for <input type=datetime-local>. */
export const toBangkokLocal = (iso: string) => new Date(new Date(iso).getTime() + 7 * 3600_000).toISOString().slice(0, 16);

export const bangkokIso = (local: string) => (local.length === 16 ? local + ":00" : local) + "+07:00";

export function groupBy<T>(items: T[], key: (t: T) => string): [string, T[]][] {
  const m = new Map<string, T[]>();
  for (const it of items) {
    const k = key(it);
    (m.get(k) ?? m.set(k, []).get(k)!).push(it);
  }
  return [...m.entries()];
}
