# Advisor Appointment API
> ส่วนนี้เป็น `backend/` ของ monorepo — หน้าเว็บอยู่ที่ `../frontend` (ดู README ที่รากโปรเจกต์)

API สำหรับระบบนัดหมายอาจารย์/ภาควิชา (FastAPI + PostgreSQL) ทุก endpoint ตรงกับปุ่มในหน้าเว็บจำลองที่ทำไว้ก่อนหน้า
กติกาสำคัญ (จองล่วงหน้า โควตา นัดซ้อน เส้นตายยกเลิก ไม่ส่งแจ้งเตือนซ้ำ) อยู่ในฟังก์ชันฐานข้อมูล ไม่ใช่ในโค้ด Python
จึงบังคับใช้เหมือนกันไม่ว่าจะมีใครเรียกจากทางไหน

## เริ่มใช้งาน

ต้องมี Python 3.11+ และ PostgreSQL 14+ (ใช้ extension `pgcrypto`, `btree_gist` ซึ่งเจ้าของฐานข้อมูลติดตั้งเองได้)

```bash
pip install -r requirements.txt
createdb advisor
export DATABASE_URL=postgresql://localhost/advisor APP_ENV=dev
./scripts/init_db.sh --seed          # schema.sql -> schema_v2.sql -> schema_v3.sql -> seed.sql (ข้อมูลตัวอย่าง)
uvicorn app.main:app --reload        # เปิด http://localhost:8000/docs
```

บัญชีตัวอย่าง (รหัสผ่านทุกบัญชี `demo1234`): `thana@example.edu`, `pimlada@example.edu` (นักศึกษา),
`sureeporn@example.edu`, `nattawut@example.edu` (อาจารย์), `mali@example.edu` (เจ้าหน้าที่)

แนะนำให้ตั้งเขตเวลาของฐานข้อมูลให้ตรงกับที่ใช้จริง เพราะ "วันนี้" ของงานเลยกำหนดและงานเตือนอิงเวลาของเซสชัน:
`ALTER DATABASE advisor SET timezone = 'Asia/Bangkok';`

## ตั้งค่า (ตัวแปรสภาพแวดล้อม)

| ตัวแปร | ความหมาย |
|---|---|
| `DATABASE_URL` | เช่น `postgresql://user:pass@host:5432/advisor` |
| `JWT_SECRET` | สตริงสุ่มยาว 32 ตัวอักษรขึ้นไป **จำเป็น** ยกเว้นตั้ง `APP_ENV=dev` (ถ้าไม่ตั้ง ระบบไม่ยอมเริ่มทำงาน) |
| `APP_ENV` | `dev` อนุญาตให้ใช้ secret ในตัวสำหรับเครื่องตัวเอง ค่าเริ่มต้นคือโหมด production |
| `JWT_TTL_MINUTES` | อายุ token ค่าเริ่มต้น 480 |
| `DB_TIMEZONE` | เขตเวลาของ connection ค่าเริ่มต้น `Asia/Bangkok` (เวลาใน JSON จะมี offset +07:00) |
| `CORS_ORIGINS` | ต้นทางของหน้าเว็บ คั่นด้วยจุลภาค เช่น `https://app.example.edu` |
| `DB_POOL_MAX` | จำนวน connection สูงสุดใน pool ค่าเริ่มต้น 10 |

## การยืนยันตัวตนและรูปแบบ error

เรียก `POST /api/v1/auth/login` ด้วย `{"email","password","role"?}` ได้ `access_token` แล้วส่งในหัว `Authorization: Bearer <token>`
ถ้าส่ง `role` ที่ไม่ตรงกับบัญชี (เหมือนเลือกแท็บผิดในหน้า login) จะได้ `403 role_mismatch`
ผิดอีเมลหรือรหัสผ่านได้คำตอบเดียวกันเสมอ (`401 invalid_credentials`) เพื่อไม่บอกว่ามีอีเมลนี้ในระบบหรือไม่

ทุก error มีรูปแบบเดียว: `{"error": {"code": "...", "message": "ข้อความไทย", "details": ...}}`
ฝั่งหน้าเว็บให้ตัดสินใจจาก `code` (คงที่) และแสดง `message` ได้ทันที

| code | HTTP | เมื่อไหร่ |
|---|---|---|
| `not_authenticated` / `invalid_token` | 401 | ไม่มี token หรือ token หมดอายุ/ไม่ถูกต้อง |
| `forbidden` | 403 | บทบาทไม่มีสิทธิ์ทำรายการนี้ |
| `*_not_found` | 404 | ไม่พบ หรือไม่ใช่ของคุณ (ไม่บอกว่ามีอยู่จริง) |
| `slot_unavailable` | 409 | ช่องถูกจองไปแล้วหรือไม่เปิดให้จอง |
| `too_late_to_book` | 409 | จองล่วงหน้าไม่ถึงที่กติกากำหนด |
| `too_many_active_appointments` | 409 | มีนัดที่รออยู่ครบโควตา |
| `student_time_conflict` | 409 | นักศึกษามีนัดอื่นที่เวลาซ้อนกัน |
| `too_late_to_cancel` | 409 | เลยเส้นตายที่นักศึกษายกเลิกเองได้ (อาจารย์ยกเลิกได้เสมอ) |
| `slot_overlaps` | 409 | เปิดช่องเวลาทับกับช่องเดิมของอาจารย์คนเดียวกัน |
| `not_active`, `too_early`, `slot_not_open`, `not_cancellable`, `appointment_cancelled` | 409 | สถานะไม่เอื้อให้ทำรายการนี้ |
| `validation_error` และ `reason_required`, `slot_in_past`, `invalid_note`, `invalid_status` | 422 | ข้อมูลที่ส่งมาไม่ถูกต้อง (`details` บอกช่องที่ผิด) |

## Endpoints

ทุกเส้นทางอยู่ใต้ `/api/v1` (ยกเว้น `/health`) ผลลัพธ์แบบรายการอยู่ในรูป `{"items": [...]}` ดูตัวอย่างข้อมูลจริงได้ที่ `/docs` หลังรัน

| วิธี | เส้นทาง | ใครเรียกได้ | ปุ่มในหน้าเว็บจำลอง |
|---|---|---|---|
| `GET` | `/health` | ทุกคน | ตรวจว่าระบบพร้อม |
| `POST` | `/api/v1/auth/login` | ทุกคน | เข้าสู่ระบบ |
| `GET` | `/api/v1/me` | ผู้ที่ login | บัตรผู้ใช้ที่เมนูซ้าย |
| `GET` | `/api/v1/advisors` | ผู้ที่ login | ตัวกรองภาควิชาในหน้าจองนัด |
| `GET` | `/api/v1/slots` | ผู้ที่ login (ขอบเขตตามบทบาท) | ตารางเวลาว่าง / รายการให้จอง |
| `POST` | `/api/v1/slots` | อาจารย์ | เปิดเวลานี้ |
| `POST` | `/api/v1/slots/{slot_id}/cancel` | อาจารย์ | ปิดช่องนี้ |
| `POST` | `/api/v1/appointments` | นักศึกษา | ยืนยันการจอง |
| `GET` | `/api/v1/appointments` | นักศึกษา, อาจารย์ | รายการนัด / นัดของฉัน |
| `GET` | `/api/v1/appointments/{appointment_id}` | ผู้ร่วมนัด | หน้ารายละเอียดนัด |
| `POST` | `/api/v1/appointments/{appointment_id}/cancel` | ผู้ร่วมนัด | ยกเลิกนัด |
| `POST` | `/api/v1/appointments/{appointment_id}/status` | อาจารย์ | ปรึกษาเสร็จสิ้น / ไม่มาตามนัด |
| `POST` | `/api/v1/appointments/{appointment_id}/notes` | อาจารย์ | บันทึก (ครั้งแรก) |
| `PATCH` | `/api/v1/notes/{note_id}` | อาจารย์ | บันทึก (แก้ไข) |
| `GET` | `/api/v1/tasks` | นักศึกษา, อาจารย์ | บอร์ดงาน |
| `POST` | `/api/v1/appointments/{appointment_id}/tasks` | อาจารย์ | มอบหมายให้… |
| `PATCH` | `/api/v1/tasks/{task_id}` | นักศึกษา, อาจารย์ | เริ่มทำ / ทำเสร็จแล้ว / ย้อนกลับ |
| `GET` | `/api/v1/notifications` | ผู้ที่ login | กล่องแจ้งเตือน + ตัวเลขบนเมนู |
| `POST` | `/api/v1/notifications/read-all` | ผู้ที่ login | ทำเครื่องหมายอ่านแล้วทั้งหมด |
| `POST` | `/api/v1/notifications/{notification_id}/read` | ผู้ที่ login | กดที่การแจ้งเตือน |
| `GET` | `/api/v1/policy` | ผู้ที่ login | แถบกติกาการจอง |
| `PUT` | `/api/v1/admin/policy` | เจ้าหน้าที่ | บันทึกกติกา |
| `GET` | `/api/v1/admin/overview` | เจ้าหน้าที่ | ภาพรวมภาควิชา |
| `POST` | `/api/v1/admin/jobs/send-reminders` | เจ้าหน้าที่ | รันงานแจ้งเตือนตอนนี้ |

พฤติกรรมที่ควรรู้
- **`GET /slots`** นักศึกษาเห็นเฉพาะช่องที่ว่างและยังไม่ถึงเวลา อาจารย์เห็นเฉพาะของตัวเอง เจ้าหน้าที่เห็นทั้งหมด กรองด้วย `advisor_id`, `department`, `status`, `from_date`, `to_date`
- **`GET /appointments?view=upcoming|past|all`** คือนัดของฉัน (ในฐานะนักศึกษาหรืออาจารย์) นัดของคนอื่นตอบ 404 ไม่ใช่ 403
- **บันทึกประเด็น** นักศึกษาเห็นเฉพาะบันทึกที่ตั้งเป็น `shared` การแชร์ครั้งแรกจะแจ้งเตือนนักศึกษาหนึ่งครั้งต่อนัด แก้ไขภายหลังไม่แจ้งซ้ำ
  `PATCH /notes/{id}` ไม่ส่งช่องไหนคือไม่แก้ช่องนั้น ส่ง `""` เพื่อล้างข้อความ
- **งาน** นักศึกษาเปลี่ยนได้เฉพาะ `status` (และไม่ใช่ `cancelled`) อาจารย์ผู้มอบหมายแก้ชื่อ รายละเอียด กำหนดส่งได้ นักศึกษาทำเสร็จแล้วอาจารย์ได้รับแจ้ง
- **เจ้าหน้าที่** เห็นเฉพาะตัวเลขและชื่อ ไม่มี endpoint ไหนให้เห็นหัวข้อนัดหรือบันทึกประเด็น
- **งานเตือนอัตโนมัติ** `POST /admin/jobs/send-reminders` เรียกซ้ำกี่ครั้งก็ไม่สร้างซ้ำ ใน production ให้ตั้งเวลาเรียกทุกชั่วโมง (cron หรือตัวตั้งเวลาของแพลตฟอร์ม)
  หรือรัน `SELECT send_reminders();` ใน psql ตรง ๆ ก็ได้

## ฐานข้อมูล

`sql/schema.sql` (4 ตารางหลัก) -> `schema_v2.sql` (กติกา การแจ้งเตือน งานเตือน สถิติ) -> `schema_v3.sql` (ส่วนที่เพิ่มตอนทำ API) ต้องรันตามลำดับ `schema_v3.sql` เพิ่ม
- `users.password_hash` สำหรับ login
- ล็อกต่อนักศึกษาใน `book_slot()` เพื่อกันการจองสองช่องพร้อมกันจนเกินโควตา (ทดสอบแล้วว่าคำขอที่สองต้องรอแล้วถูกปฏิเสธ)
- ตรวจว่าผู้จองเป็นนักศึกษาจริง และกันนัดซ้อนเวลาของนักศึกษาคนเดียวกัน
- `cancel_appointment()` ตรวจว่าผู้ยกเลิกเป็นนักศึกษาหรืออาจารย์ของนัดนั้นจริง (ก่อนหน้านี้ฟังก์ชันเชื่อ user id ที่ส่งมาโดยไม่ตรวจ)

เพิ่มผู้ใช้เอง: สร้าง hash ด้วย `python -m app.security 'รหัสผ่าน'` แล้วใส่ในคอลัมน์ `password_hash` (รูปแบบ scrypt จาก standard library ไม่ต้องติดตั้งเพิ่ม)

## ทดสอบ

```bash
pytest                                                    # 11 ข้อแรกไม่ต้องใช้ฐานข้อมูล ที่เหลือจะข้ามเองถ้าไม่ได้ตั้งตัวแปรถัดไป
createdb advisor_test
TEST_DATABASE_URL=postgresql://localhost/advisor_test pytest   # 33 ข้อ HTTP-level
```

ชื่อฐานข้อมูลทดสอบต้องลงท้ายด้วย `_test` ชุดทดสอบจะล้างและสร้างตารางใหม่ทุกครั้ง และโหลด `seed.sql` ก่อนทุกเทสต์

## สถานะการตรวจสอบ

ตรวจแล้ว (รันจริง):
- `schema_v3.sql` และฟังก์ชันทั้งหมดบน PostgreSQL 16 รวมถึงการจองพร้อมกันสองเซสชัน
- โค้ดของแอปทั้งหมดรันกับ PostgreSQL 16 จริง ผ่านเทสต์ 44 ข้อ (ลำดับปกติและลำดับย้อนกลับ)

ยังไม่ได้ตรวจ: ผมรันบนเครื่องที่ติดตั้งแพ็กเกจจาก PyPI ไม่ได้ จึงใช้ตัวจำลอง FastAPI และ psycopg แบบบางที่เขียนเฉพาะสำหรับทดสอบ (ไม่รวมอยู่ในโปรเจกต์นี้)
ดังนั้นส่วนที่ยังไม่เคยรันกับของจริงคือการผูกเส้นทางและ dependency ของ FastAPI, การสร้างหน้า `/docs`, และพฤติกรรมของ `psycopg_pool`
เทสต์ชุดเดียวกันนี้เขียนเป็นระดับ HTTP จึงรันกับ FastAPI จริงได้ทันที รัน `pytest` เป็นอย่างแรกบนเครื่องคุณ ถ้ามีข้อไหนล้ม จุดที่น่าสงสัยก่อนคือ `app/db.py` และ `app/main.py`

ข้อจำกัดของ MVP: ยังไม่มี rate limit ที่หน้า login, ไม่มี endpoint จัดการผู้ใช้ (เพิ่มผ่าน SQL), และไม่มีการส่งอีเมล/LINE (การแจ้งเตือนเข้ากล่องในระบบ)
