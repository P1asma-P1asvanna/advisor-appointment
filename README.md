# นัดหมายอาจารย์ (Advisor Appointment)

ระบบจองนัดปรึกษาอาจารย์/ภาควิชา แบบ MVP: อาจารย์เปิดเวลาว่าง → นักศึกษาจอง → อาจารย์บันทึกประเด็นหลังพบ → มอบงานติดตาม  
มี 3 บทบาท: **นักศึกษา**, **อาจารย์**, **เจ้าหน้าที่ภาควิชา** (เห็นเฉพาะจำนวนและชื่อ ไม่เห็นหัวข้อหรือบันทึกการปรึกษา)

```
advisor-appointment/
├── backend/            FastAPI + PostgreSQL (API 24 เส้นทาง, SQL schema, เทสต์)  → ดู backend/README.md
├── frontend/           React + Vite + TypeScript (หน้าเว็บจริง)
│   └── src/
│       ├── api/        client.ts (fetch + จัดการ error), endpoints.ts, types.ts
│       ├── auth/       AuthContext (login/logout, token)
│       ├── components/ Layout, Toast, ui (Badge, Modal, Tabs ฯลฯ)
│       ├── lib/        format (เวลาไทย/Asia/Bangkok), labels, hooks
│       ├── pages/      student/ advisor/ admin/ shared/ และ Login
│       └── styles/     global.css
├── docker-compose.yml  PostgreSQL + API สำหรับลองในเครื่อง
└── .github/workflows/  CI: build หน้าเว็บ + รันเทสต์ backend
```

## เริ่มใช้งานในเครื่อง

ต้องมี Docker, Node 20+ (Python 3.12 เฉพาะกรณีรัน backend โดยไม่ใช้ Docker)

```bash
docker compose up --build        # ฐานข้อมูล + API ที่ http://localhost:8000 (โหลดข้อมูลตัวอย่างให้)
cd frontend
npm install
npm run dev                      # เว็บที่ http://localhost:5173 (proxy /api ไปที่ :8000)
```

บัญชีตัวอย่าง (มีเฉพาะฐานข้อมูลที่โหลด `seed.sql`) รหัสผ่าน `demo1234` ทุกบัญชี ใส่เองในหน้าล็อกอิน

| บทบาท | อีเมล |
|---|---|
| นักศึกษา | thana@example.edu, pimlada@example.edu |
| อาจารย์ | sureeporn@example.edu, nattawut@example.edu |
| เจ้าหน้าที่ | mali@example.edu |

## หน้าเว็บ

| บทบาท | หน้า |
|---|---|
| นักศึกษา | จองนัดหมาย (กรองภาควิชา/อาจารย์, เห็นกติกา) · นัดของฉัน (ยกเลิกพร้อมเหตุผล, **แก้หัวข้อก่อนถึงเวลานัด**) · **ปฏิทินรายเดือน** · รายละเอียดนัด (บันทึกที่แชร์ + งาน) · งานติดตาม (กระดาน 3 คอลัมน์) · การแจ้งเตือน |
| อาจารย์ | เวลาว่างของฉัน (เปิด/**แก้ไข**/ปิดช่อง) · นัดหมาย (เสร็จสิ้น/ไม่มา/ยกเลิก) · **ปฏิทินรายเดือน** · รายละเอียดนัด (บันทึกประเด็น แชร์/ส่วนตัว, มอบงาน) · งานที่มอบหมาย · การแจ้งเตือน |
| เจ้าหน้าที่ | ภาพรวมภาควิชา (KPI, รายอาจารย์, นักศึกษาที่ควรติดตาม, รันแจ้งเตือน) · **จัดการผู้ใช้** (เพิ่ม, **แก้ไขชื่อ/อีเมล/บทบาท/ภาควิชา**, ปิด/เปิดบัญชี, รีเซ็ตรหัสผ่าน) · กติกาการจอง |
| ทุกบทบาท | **บัญชีของฉัน** (เปลี่ยนรหัสผ่าน) บัญชีใหม่หรือถูกรีเซ็ตจะถูกบังคับให้ตั้งรหัสผ่านใหม่ก่อนใช้งาน |

ทุกข้อความ error ที่แสดงมาจาก API โดยตรง (ภาษาไทย) เช่น "ช่องถูกจองไปแล้ว" แล้วหน้าจะรีเฟรชรายการให้เอง

## Deploy (Neon + Render + Vercel)

| ส่วน | บริการ | ค่าที่ต้องตั้ง |
|---|---|---|
| ฐานข้อมูล | Neon (connection string แบบ **ไม่ใช่ pooled**) | รัน `backend/sql/schema*.sql` ตามลำดับ |
| API | Render, Root Directory `backend` | `DATABASE_URL`, `JWT_SECRET` (สุ่ม 32+ ตัวอักษร), `CORS_ORIGINS` (ที่อยู่เว็บ ไม่มี `/` ท้าย), Health Check `/health`, อย่าตั้ง `APP_ENV=dev` |
| เว็บ | Vercel, Root Directory `frontend` | `VITE_API_URL` (ที่อยู่ API ไม่มี `/` ท้าย) ไฟล์ `frontend/vercel.json` ทำให้ทุกเส้นทางชี้ไป `index.html` |

ตั้ง scheduler เรียก `POST /api/v1/admin/jobs/send-reminders` (หรือ `SELECT send_reminders();`) ทุกชั่วโมงถ้าต้องการแจ้งเตือนอัตโนมัติ

### อัปเกรดระบบที่ขึ้นแล้วเป็นรุ่นมีระบบผู้ใช้ (schema_v4)
ลำดับสำคัญ เพื่อไม่ให้ระบบที่ใช้งานอยู่พัง
1. Neon SQL Editor: รัน `backend/sql/schema_v4.sql` ก่อน (รันซ้ำได้ ไม่กระทบข้อมูลเดิม)
2. Render: เพิ่ม `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` (8+ ตัว), `BOOTSTRAP_ADMIN_NAME`
3. push โค้ดขึ้น GitHub ให้ Render และ Vercel deploy ใหม่
4. เมื่อพร้อมใช้งานจริง: Neon SQL Editor รัน `backend/sql/clear_demo_data.sql` (**ลบข้อมูลตัวอย่างทั้งหมด**) แล้วที่ Render กด Manual Deploy → Restart เพื่อให้ระบบสร้างเจ้าหน้าที่คนแรกจากข้อ 2
5. ล็อกอินด้วยบัญชีนั้น ตั้งรหัสผ่านใหม่ แล้วที่ Render ลบตัวแปร `BOOTSTRAP_ADMIN_PASSWORD` ออก

### ใช้ชื่อโดเมนของตัวเอง
1. ซื้อโดเมนจากผู้ให้บริการใดก็ได้
2. Vercel → โปรเจกต์ → Settings → Domains → Add แล้วตั้งค่า DNS ที่ผู้ให้บริการโดเมนตามที่ Vercel แสดง (ปกติเป็น A หรือ CNAME) รอจนขึ้น Valid Configuration
3. Render → Environment: เพิ่มโดเมนใหม่ใน `CORS_ORIGINS` คั่นด้วยจุลภาค เช่น `https://app.example.edu,https://advisor-appointment.vercel.app`
4. (ไม่บังคับ) โดเมนให้ API ด้วย: Render → Settings → Custom Domains แล้วเปลี่ยน `VITE_API_URL` ที่ Vercel เป็นที่อยู่ใหม่ และ Redeploy

## สถานะการตรวจสอบ (ตรงไปตรงมา)

- Backend: เทสต์ 70 ข้อผ่านบน PostgreSQL 16 จริง ส่วนที่ผูกกับ FastAPI/psycopg จริงตรวจผ่าน CI และใช้งานจริงบน Render แล้ว
- Frontend: build ผ่านบนเครื่องผู้ใช้ และเปิดใช้งานจริงบน Vercel แล้ว หน้าที่เพิ่มใหม่ (จัดการผู้ใช้, บัญชีของฉัน) ตรวจ syntax แล้ว แต่ต้อง build และลองกดใช้งานบนเครื่องจริงก่อน
- ข้อจำกัด: ลืมรหัสผ่านด้วยตัวเอง, และแจ้งเตือนทางอีเมล/LINE
