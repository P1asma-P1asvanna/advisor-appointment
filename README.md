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

บัญชีตัวอย่าง รหัสผ่าน `demo1234` ทุกบัญชี

| บทบาท | อีเมล |
|---|---|
| นักศึกษา | thana@example.edu, pimlada@example.edu |
| อาจารย์ | sureeporn@example.edu, nattawut@example.edu |
| เจ้าหน้าที่ | mali@example.edu |

## หน้าเว็บ

| บทบาท | หน้า |
|---|---|
| นักศึกษา | จองนัดหมาย (กรองภาควิชา/อาจารย์, เห็นกติกา) · นัดของฉัน (ยกเลิกพร้อมเหตุผล) · รายละเอียดนัด (บันทึกที่แชร์ + งาน) · งานติดตาม (กระดาน 3 คอลัมน์) · การแจ้งเตือน |
| อาจารย์ | เวลาว่างของฉัน (เปิด/ปิดช่อง) · นัดหมาย (เสร็จสิ้น/ไม่มา/ยกเลิก) · รายละเอียดนัด (บันทึกประเด็น แชร์/ส่วนตัว, มอบงาน) · งานที่มอบหมาย · การแจ้งเตือน |
| เจ้าหน้าที่ | ภาพรวมภาควิชา (KPI, รายอาจารย์, นักศึกษาที่ควรติดตาม, รันแจ้งเตือน) · กติกาการจอง |

ทุกข้อความ error ที่แสดงมาจาก API โดยตรง (ภาษาไทย) เช่น "ช่องถูกจองไปแล้ว" แล้วหน้าจะรีเฟรชรายการให้เอง

## ตั้งค่าตอน deploy

- **Frontend**: `npm run build` ได้โฟลเดอร์ `frontend/dist` (โฮสต์แบบ static ได้ เช่น Netlify/Vercel/Cloudflare Pages) ตั้ง `VITE_API_URL` เป็นที่อยู่ API แล้วตั้ง `VITE_SHOW_DEMO=false`
  ต้องตั้ง rewrite ให้ทุกเส้นทางชี้ไป `index.html` (SPA)
- **Backend**: ตั้ง `JWT_SECRET` (สุ่ม 32+ ตัวอักษร), `DATABASE_URL`, `CORS_ORIGINS` เป็น origin ของเว็บ และอย่าตั้ง `APP_ENV=dev`; ลบ `seed.sql` ออกจากการ init
- ตั้ง scheduler เรียก `POST /api/v1/admin/jobs/send-reminders` (หรือ `SELECT send_reminders();`) ทุกชั่วโมง

## สถานะการตรวจสอบ (ตรงไปตรงมา)

- Backend: เทสต์ 44 ข้อผ่านบน PostgreSQL 16 จริง แต่รันกับตัวจำลอง FastAPI/psycopg เพราะสภาพแวดล้อมที่พัฒนาติดตั้ง PyPI ไม่ได้ → ให้ดู CI ว่าเขียวกับไลบรารีจริง
- Frontend: ตรวจ syntax ของทุกไฟล์ และตรวจชนิดข้อมูลของชั้น `api/` กับ `lib/` แล้ว แต่ **ยังไม่เคยรัน `npm install`/`npm run build` หรือเปิดในเบราว์เซอร์** (npm ถูกบล็อก) หน้า React จึงยังไม่ผ่านการ type-check เต็มรูปแบบ — รัน `npm run build` ก่อนใช้งาน ถ้ามี error ส่งมาแก้ได้ทันที
