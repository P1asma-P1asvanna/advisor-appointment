// Reading a CSV the way people actually make them: from Excel, with Thai text, with a header row.

export interface ImportRow {
  email: string;
  full_name: string;
  role: string;
  department: string;
  password: string;
}

export const MAX_IMPORT_ROWS = 300;

/** Decode file bytes. Excel's "CSV UTF-8" is UTF-8; its plain "CSV" saves Thai as Windows-874. */
export function decodeCsv(buf: ArrayBuffer): string {
  let text: string;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(buf);
  } catch {
    try {
      text = new TextDecoder("windows-874").decode(buf);
    } catch {
      text = new TextDecoder("utf-8").decode(buf);
    }
  }
  return text.replace(/^﻿/, "");
}

function detectDelimiter(firstLine: string): string {
  const count = (c: string) => firstLine.split(c).length - 1;
  const best = [",", ";", "\t"].map((d) => [d, count(d)] as const).sort((a, b) => b[1] - a[1])[0];
  return best[1] > 0 ? best[0] : ",";
}

/** RFC-4180-style parser: quoted cells, "" for a quote, line breaks inside quotes, CRLF or LF. */
export function parseCsv(text: string): string[][] {
  const firstLine = text.split(/\r?\n/, 1)[0] ?? "";
  const delim = detectDelimiter(firstLine);
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"') {
        if (text[i + 1] === '"') { cell += '"'; i++; } else quoted = false;
      } else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === delim) { row.push(cell); cell = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cell); cell = "";
      rows.push(row); row = [];
    } else cell += ch;
  }
  if (cell !== "" || row.length) { row.push(cell); rows.push(row); }
  return rows.filter((r) => r.some((c) => c.trim() !== "")); // drop blank lines
}

const ALIASES: Record<keyof ImportRow, string[]> = {
  email: ["email", "e-mail", "mail", "อีเมล", "อีเมลล์", "อีเมล์"],
  full_name: ["fullname", "name", "ชื่อ", "ชื่อนามสกุล", "ชื่อสกุล", "ชื่อ-นามสกุล"],
  department: ["department", "dept", "ภาควิชา", "สาขา", "สาขาวิชา"],
  role: ["role", "บทบาท", "ประเภท"],
  password: ["password", "รหัสผ่าน"],
};
const norm = (h: string) => h.trim().toLowerCase().replace(/[\s_\-.]/g, "");
const LOOKUP = new Map<string, keyof ImportRow>();
for (const [field, names] of Object.entries(ALIASES) as [keyof ImportRow, string[]][])
  for (const n of names) LOOKUP.set(norm(n), field);

export type CsvResult = { rows: ImportRow[]; error?: undefined } | { rows?: undefined; error: string };

/** The first line must be a header naming the columns (Thai or English). Needs email and full name. */
export function rowsFromCsv(text: string): CsvResult {
  const table = parseCsv(text);
  if (table.length === 0) return { error: "ไม่พบข้อมูลในไฟล์" };
  const cols = table[0].map((h) => LOOKUP.get(norm(h)));
  if (!cols.includes("email") || !cols.includes("full_name"))
    return { error: "แถวแรกต้องเป็นหัวตารางที่มีคอลัมน์ อีเมล (email) และ ชื่อ-นามสกุล (full_name) ดาวน์โหลดไฟล์แม่แบบเพื่อดูตัวอย่างได้" };
  if (table.length === 1) return { error: "มีแต่หัวตาราง ยังไม่มีข้อมูลผู้ใช้" };
  if (table.length - 1 > MAX_IMPORT_ROWS) return { error: `นำเข้าได้ครั้งละไม่เกิน ${MAX_IMPORT_ROWS} คน ไฟล์นี้มี ${table.length - 1} แถว กรุณาแบ่งไฟล์` };
  const rows = table.slice(1).map((cells) => {
    const r: ImportRow = { email: "", full_name: "", role: "", department: "", password: "" };
    cols.forEach((f, i) => { if (f) r[f] = (cells[i] ?? "").trim(); });
    return r;
  });
  return { rows };
}

export const TEMPLATE_CSV =
  "email,full_name,department,role\n" +
  "somchai@example.edu,สมชาย ใจดี,วิศวกรรมคอมพิวเตอร์,นักศึกษา\n" +
  "somying@example.edu,สมหญิง ศรีสุข,วิศวกรรมคอมพิวเตอร์,นักศึกษา\n" +
  "ajarn.a@example.edu,อ.อรุณ แสงทอง,วิศวกรรมคอมพิวเตอร์,อาจารย์\n";

/** Build a CSV string, quoting cells that need it. */
export function toCsv(table: string[][]): string {
  return table.map((r) => r.map((c) => (/[",\r\n]/.test(c) ? `"${c.replace(/"/g, '""')}"` : c)).join(",")).join("\r\n") + "\r\n";
}

/** Download text as a file. The BOM makes Excel read Thai correctly. */
export function downloadText(filename: string, text: string) {
  const blob = new Blob(["﻿", text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
