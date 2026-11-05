import type { Appointment } from "../api/types";

const utc = (iso: string) => new Date(iso).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");

/** A "add to Google Calendar" link (opens Google's own prefilled form; no sign-in or API needed on our side). */
export function googleCalendarUrl(a: Appointment, role: "student" | "advisor"): string {
  const other = role === "advisor" ? a.student.name : a.advisor.name;
  const where = a.mode === "onsite" ? a.location ?? "" : a.meeting_url ?? "ออนไลน์";
  const details = [`หัวข้อ: ${a.topic}`, `${role === "advisor" ? "นักศึกษา" : "อาจารย์"}: ${other}`];
  if (a.mode !== "onsite" && a.meeting_url) details.push(`ลิงก์ประชุม: ${a.meeting_url}`);
  const q = new URLSearchParams({
    action: "TEMPLATE",
    text: role === "advisor" ? `นัดพบนักศึกษา: ${other}` : `นัดพบอาจารย์ที่ปรึกษา: ${other}`,
    dates: `${utc(a.starts_at)}/${utc(a.ends_at)}`,
    details: details.join("\n"),
    location: where,
  });
  return "https://calendar.google.com/calendar/render?" + q.toString();
}
