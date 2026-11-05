import { ChangeEvent, useState } from "react";
import { api } from "../../api/endpoints";
import type { ImportResult } from "../../api/types";
import { Badge, Modal } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { ImportRow, MAX_IMPORT_ROWS, TEMPLATE_CSV, decodeCsv, downloadText, rowsFromCsv, toCsv } from "../../lib/csv";
import { ROLE_TH } from "../../lib/labels";
import type { Role } from "../../api/types";

type Stage = "input" | "preview" | "done";

export default function ImportUsersModal({ onClose, onDone }: { onClose(): void; onDone(): void }) {
  const toast = useToast();
  const [stage, setStage] = useState<Stage>("input");
  const [text, setText] = useState("");
  const [fileName, setFileName] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [rows, setRows] = useState<ImportRow[]>([]);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function pickFile(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setFileName(f.name);
    setText(decodeCsv(await f.arrayBuffer()));
    setProblem(null);
  }

  async function check() {
    const parsed = rowsFromCsv(text);
    if (parsed.error !== undefined) return setProblem(parsed.error);
    setProblem(null);
    setBusy(true);
    try {
      setRows(parsed.rows);
      setResult(await api.importUsers(parsed.rows, true));
      setStage("preview");
    } catch (err: any) {
      setProblem(err?.message ?? "ตรวจไฟล์ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function run() {
    setBusy(true);
    try {
      const r = await api.importUsers(rows, false);
      setResult(r);
      setStage("done");
      toast.ok(`สร้างบัญชีแล้ว ${r.summary.created} คน`);
      onDone();
    } catch (err) {
      toast.fail(err);
    } finally {
      setBusy(false);
    }
  }

  const roleLabel = (r: string) => (r in ROLE_TH ? ROLE_TH[r as Role] : r || "–");
  const created = result?.rows.filter((r) => r.password) ?? [];

  return (
    <Modal title="นำเข้าผู้ใช้จากไฟล์ CSV" onClose={onClose} wide>
      {stage === "input" && (
        <>
          <ol className="muted">
            <li>เตรียมไฟล์ที่แถวแรกเป็นหัวตาราง คอลัมน์ที่ต้องมีคือ <b>email</b> และ <b>full_name</b> (หรือ อีเมล, ชื่อ-นามสกุล) ส่วน <b>department</b> (ภาควิชา) จำเป็นสำหรับนักศึกษาและอาจารย์ ส่วน <b>role</b> (บทบาท) ถ้าไม่ใส่จะเป็นนักศึกษา และ <b>password</b> ถ้าไม่ใส่ระบบสุ่มรหัสชั่วคราวให้</li>
            <li>จาก Excel ให้เลือก บันทึกเป็น <b>CSV UTF-8</b> เพื่อให้ภาษาไทยไม่เพี้ยน (ระบบลองแก้ให้ถ้าเป็น CSV แบบเก่า)</li>
            <li>นำเข้าได้ครั้งละไม่เกิน {MAX_IMPORT_ROWS} คน</li>
          </ol>
          <div className="drop">
            <div className="row wrap">
              <input type="file" accept=".csv,.txt,text/csv" onChange={pickFile} />
              <button className="btn sm" onClick={() => downloadText("แม่แบบนำเข้าผู้ใช้.csv", TEMPLATE_CSV)}>ดาวน์โหลดไฟล์แม่แบบ</button>
            </div>
            {fileName && <span className="muted">ไฟล์: {fileName}</span>}
          </div>
          <label className="field"><span>หรือวางข้อมูลที่คัดลอกจาก Excel / Google Sheets (รวมแถวหัวตาราง)</span>
            <textarea rows={6} value={text} onChange={(e) => { setText(e.target.value); setFileName(""); }} placeholder={"email,full_name,department\nsomchai@example.edu,สมชาย ใจดี,วิศวกรรมคอมพิวเตอร์"} />
          </label>
          {problem && <div className="form-error" role="alert">{problem}</div>}
          <div className="row end">
            <button className="btn" onClick={onClose}>ยกเลิก</button>
            <button className="btn primary" disabled={busy || !text.trim()} onClick={check}>{busy ? "กำลังตรวจ…" : "ตรวจสอบไฟล์"}</button>
          </div>
        </>
      )}

      {stage === "preview" && result && (
        <>
          <div className="summary">
            <Badge tone="gray">ทั้งหมด {result.summary.total} แถว</Badge>
            <Badge tone="green">พร้อมนำเข้า {result.summary.ok}</Badge>
            {result.summary.errors > 0 && <Badge tone="red">มีปัญหา {result.summary.errors} (จะข้ามแถวเหล่านี้)</Badge>}
          </div>
          <p className="muted">ยังไม่มีการสร้างบัญชีจริง ตรวจรายการด้านล่างแล้วกดนำเข้า</p>
          <div className="table-wrap import-table">
            <table>
              <thead><tr><th>#</th><th>อีเมล</th><th>ชื่อ</th><th>บทบาท</th><th>ภาควิชา</th><th>ผลตรวจ</th></tr></thead>
              <tbody>
                {result.rows.map((r) => (
                  <tr key={r.index} className={r.status === "error" ? "bad" : ""}>
                    <td>{r.index + 2}</td>
                    <td>{r.email || "–"}</td>
                    <td>{r.full_name || "–"}</td>
                    <td>{roleLabel(r.role)}</td>
                    <td>{r.department ?? "–"}</td>
                    <td>{r.status === "ok" ? <Badge tone="green">พร้อม</Badge> : r.error}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted">เลข # คือเลขแถวในไฟล์ (แถวแรกคือหัวตาราง)</p>
          <div className="row end">
            <button className="btn" onClick={() => setStage("input")}>← แก้ไฟล์</button>
            <button className="btn primary" disabled={busy || result.summary.ok === 0} onClick={run}>
              {busy ? "กำลังนำเข้า…" : `นำเข้า ${result.summary.ok} คน`}
            </button>
          </div>
        </>
      )}

      {stage === "done" && result && (
        <>
          <div className="summary">
            <Badge tone="green">สร้างแล้ว {result.summary.created} คน</Badge>
            {result.summary.errors > 0 && <Badge tone="red">ข้าม {result.summary.errors} แถว</Badge>}
          </div>
          <div className="notice warn">รหัสผ่านชั่วคราวด้านล่างแสดง<b>ครั้งเดียว</b> ดาวน์โหลดเก็บไว้เดี๋ยวนี้ แล้วส่งให้แต่ละคน (ทุกคนต้องตั้งรหัสใหม่ของตัวเองตอนเข้าสู่ระบบครั้งแรก) ถ้าทำหายให้กดรีเซ็ตรหัสผ่านรายคนในหน้าจัดการผู้ใช้</div>
          <div className="row end" style={{ marginTop: 0, marginBottom: ".5rem" }}>
            <button
              className="btn primary"
              onClick={() => downloadText("รหัสผ่านชั่วคราว.csv", toCsv([["email", "full_name", "role", "temporary_password"], ...created.map((r) => [r.email, r.full_name, roleLabel(r.role), r.password ?? ""])]))}
            >
              ดาวน์โหลดรหัสผ่านชั่วคราว (CSV)
            </button>
          </div>
          <div className="table-wrap import-table">
            <table>
              <thead><tr><th>อีเมล</th><th>ชื่อ</th><th>บทบาท</th><th>รหัสผ่านชั่วคราว</th></tr></thead>
              <tbody>
                {created.map((r) => (
                  <tr key={r.index}><td>{r.email}</td><td>{r.full_name}</td><td>{roleLabel(r.role)}</td><td className="mono">{r.password}</td></tr>
                ))}
                {result.rows.filter((r) => r.status === "error").map((r) => (
                  <tr key={"e" + r.index} className="bad"><td>{r.email || "–"}</td><td>{r.full_name || "–"}</td><td colSpan={2}>ข้าม (แถว {r.index + 2}): {r.error}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="row end"><button className="btn primary" onClick={onClose}>เรียบร้อย</button></div>
        </>
      )}
    </Modal>
  );
}
