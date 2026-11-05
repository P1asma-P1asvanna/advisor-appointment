import { ReactNode, useEffect, useState } from "react";
import { APPT_STATUS, SLOT_STATUS } from "../lib/labels";
import type { AppointmentStatus, Mode, SlotStatus } from "../api/types";

export const Badge = ({ tone, children }: { tone: string; children: ReactNode }) => <span className={"badge " + tone}>{children}</span>;
export const ApptBadge = ({ s }: { s: AppointmentStatus }) => <Badge tone={APPT_STATUS[s].tone}>{APPT_STATUS[s].label}</Badge>;
export const SlotBadge = ({ s }: { s: SlotStatus }) => <Badge tone={SLOT_STATUS[s].tone}>{SLOT_STATUS[s].label}</Badge>;

export const Where = ({ mode, location, url }: { mode: Mode; location: string | null; url: string | null }) =>
  mode === "online" ? (
    <span>ออนไลน์{url ? <> · <a href={url} target="_blank" rel="noreferrer">ลิงก์ประชุม</a></> : null}</span>
  ) : (
    <span>{location ? "ที่ " + location : "ที่ห้องอาจารย์"}</span>
  );

export function PageHeader({ title, sub, actions }: { title: string; sub?: string; actions?: ReactNode }) {
  return (
    <header className="page-head">
      <div>
        <h1>{title}</h1>
        {sub && <p className="muted">{sub}</p>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </header>
  );
}

export const Loading = () => <div className="state">กำลังโหลด…</div>;
export const ErrorBox = ({ message, retry }: { message: string; retry?: () => void }) => (
  <div className="state err">
    {message}
    {retry && <button className="btn sm" onClick={retry}>ลองใหม่</button>}
  </div>
);
export const Empty = ({ title, hint }: { title: string; hint?: string }) => (
  <div className="state">
    <strong>{title}</strong>
    {hint && <span className="muted">{hint}</span>}
  </div>
);

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange(v: T): void; items: [T, string][] }) {
  return (
    <div className="tabs" role="tablist">
      {items.map(([k, label]) => (
        <button key={k} role="tab" aria-selected={value === k} className={value === k ? "on" : ""} onClick={() => onChange(k)}>
          {label}
        </button>
      ))}
    </div>
  );
}

export function Modal({ title, onClose, children, wide }: { title: string; onClose(): void; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={"modal" + (wide ? " wide" : "")} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="ปิด">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

/** A small "reason" dialog used for cancelling. */
export function ReasonModal({ title, label, confirmLabel, onConfirm, onClose }: {
  title: string; label: string; confirmLabel: string; onConfirm(reason: string): Promise<void>; onClose(): void;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <Modal title={title} onClose={onClose}>
      <label className="field">
        <span>{label}</span>
        <textarea rows={3} value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} />
      </label>
      <div className="row end">
        <button className="btn" onClick={onClose}>ไม่ใช่ตอนนี้</button>
        <button className="btn danger" disabled={busy} onClick={async () => { setBusy(true); try { await onConfirm(reason); } finally { setBusy(false); } }}>
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
