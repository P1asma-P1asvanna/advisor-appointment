import type { AppointmentStatus, Role, SlotStatus, TaskStatus } from "../api/types";

export const ROLE_TH: Record<Role, string> = { student: "นักศึกษา", advisor: "อาจารย์", admin: "เจ้าหน้าที่" };

export const APPT_STATUS: Record<AppointmentStatus, { label: string; tone: string }> = {
  pending: { label: "รอยืนยัน", tone: "amber" },
  confirmed: { label: "ยืนยันแล้ว", tone: "teal" },
  completed: { label: "เสร็จสิ้น", tone: "green" },
  cancelled: { label: "ยกเลิก", tone: "gray" },
  no_show: { label: "ไม่มาตามนัด", tone: "red" },
};

export const SLOT_STATUS: Record<SlotStatus, { label: string; tone: string }> = {
  open: { label: "ว่าง", tone: "green" },
  booked: { label: "ถูกจองแล้ว", tone: "teal" },
  cancelled: { label: "ปิดแล้ว", tone: "gray" },
};

export const TASK_STATUS: Record<TaskStatus, string> = { todo: "ต้องทำ", doing: "กำลังทำ", done: "เสร็จแล้ว", cancelled: "ยกเลิก" };
