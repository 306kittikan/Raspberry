-- ============================================================
-- ตู้บริการข้อมูลอัจฉริยะ · สาขาวิชาวิทยาการคอมพิวเตอร์ ม.แม่โจ้
-- โครงสร้างฐานข้อมูล SQLite
--
-- หลักการสำคัญที่บังคับไว้ในระดับ schema (ไม่ใช่แค่ในโค้ด):
--   1. face_embeddings.consent_id เป็น NOT NULL + FK  →  เขียนเวกเตอร์ใบหน้า
--      โดยไม่มีความยินยอมไม่ได้เลย และการถอนความยินยอมลบเวกเตอร์ตามไปด้วย
--   2. ไม่มีคอลัมน์ใดเก็บ "ภาพ" ใบหน้า เก็บได้เฉพาะเวกเตอร์
--   3. usage_events ไม่มี FK ไปยัง students  →  สถิติไม่ผูกกับตัวบุคคล
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- ข้อมูลสาขา (แถวเดียว)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS department (
  id               INTEGER PRIMARY KEY CHECK (id = 1),
  name             TEXT NOT NULL,
  faculty          TEXT NOT NULL,
  abbr             TEXT NOT NULL,
  website          TEXT,
  -- ข้อมูลด้านล่างมาจากเว็บไซต์ของสาขา ช่องที่ยังไม่มีข้อมูลต้องเป็น NULL
  -- ไม่ใช่ข้อความที่ระบบแต่งขึ้นเอง เพราะตู้ที่บอกที่ตั้งผิดแย่กว่าตู้ที่ไม่ตอบ
  office_location  TEXT,
  office_hours     TEXT,
  office_phone     TEXT,
  office_email     TEXT
);

-- ------------------------------------------------------------
-- ช่องทางติดต่อ (จากเว็บไซต์ของสาขา)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS contacts (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id    TEXT UNIQUE,
  type         TEXT NOT NULL,                    -- email | phone | url | address | fax
  title        TEXT NOT NULL,
  description  TEXT,
  value        TEXT NOT NULL,
  label        TEXT,
  sort_order   INTEGER NOT NULL DEFAULT 0
);

-- ------------------------------------------------------------
-- ภาคการศึกษา
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS terms (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  code             TEXT NOT NULL UNIQUE,        -- '2569-1'
  label            TEXT NOT NULL,               -- 'ภาคการศึกษาที่ 1 ปีการศึกษา 2569'
  is_current       INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0, 1)),
  data_updated_at  TEXT                         -- ISO8601 เวลาที่นำเข้าตารางเรียนล่าสุด
);
-- มีภาคการศึกษาปัจจุบันได้ทีละภาคเดียว
CREATE UNIQUE INDEX IF NOT EXISTS ix_terms_current
  ON terms (is_current) WHERE is_current = 1;

-- ------------------------------------------------------------
-- ประกาศของสาขา (วนแสดงบนหน้าจอพัก)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS announcements (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  tag         TEXT NOT NULL,
  title       TEXT NOT NULL,
  detail      TEXT NOT NULL,
  starts_on   TEXT,                             -- ISO date, NULL = แสดงทันที
  ends_on     TEXT,                             -- ISO date, NULL = ไม่มีวันหมดอายุ
  sort_order  INTEGER NOT NULL DEFAULT 0,
  active      INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

-- ------------------------------------------------------------
-- นักศึกษา · รายวิชา · ห้องเรียน
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id   TEXT NOT NULL UNIQUE,            -- รหัสนักศึกษา
  prefix       TEXT,                            -- 'นาย' | 'นางสาว' | 'นาง'
  name         TEXT NOT NULL,                   -- ชื่อ-สกุล ไม่รวมคำนำหน้า
  -- 1 = นักศึกษาสมมติสำหรับสาธิต ยังไม่ได้เชื่อมกับระบบทะเบียนจริง
  is_synthetic INTEGER NOT NULL DEFAULT 0 CHECK (is_synthetic IN (0, 1)),
  year         INTEGER,
  entry_year   INTEGER,                         -- ปีการศึกษาที่เข้า (พ.ศ.)
  program      TEXT,
  program_code TEXT,                            -- รหัสหลักสูตรของมหาวิทยาลัย
  advisor      TEXT,
  -- สถานภาพจากระบบทะเบียน เช่น '10' = กำลังศึกษา, '50' = ลาออก
  status_code  TEXT,
  status_label TEXT,
  -- 0 = ใช้ตู้ไม่ได้ (ลาออก พ้นสภาพ หมดสภาพ) ตู้ต้องไม่แสดงข้อมูลให้คนกลุ่มนี้
  active       INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at   TEXT NOT NULL,
  updated_at   TEXT
);
-- index ของคอลัมน์ active สร้างใน app/migrations.py
-- เพราะบนฐานข้อมูลเดิม คอลัมน์นี้ยังไม่มีตอน schema.sql ทำงาน

CREATE TABLE IF NOT EXISTS courses (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id      TEXT UNIQUE,
  code           TEXT NOT NULL UNIQUE,          -- '10301141-68'
  name           TEXT NOT NULL,
  name_en        TEXT,
  credits        INTEGER,
  credit_format  TEXT,                          -- '3(2-3-5)'
  description    TEXT
);

CREATE TABLE IF NOT EXISTS buildings (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id  TEXT UNIQUE,
  name       TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS rooms (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id    TEXT UNIQUE,
  code         TEXT NOT NULL UNIQUE,            -- รหัสห้องในระบบของสาขา
  name         TEXT NOT NULL,                   -- 'ห้องปฏิบัติการคอมพิวเตอร์ 3 (Lab 3)'
  short_name   TEXT,                            -- 'Lab 3' — ใช้แสดงบนจอขนาดใหญ่
  room_type    TEXT,                            -- 'ห้องบรรยาย' | 'ห้องปฏิบัติการ'
  building_id  INTEGER REFERENCES buildings(id) ON DELETE SET NULL,
  floor        INTEGER,
  capacity     INTEGER,
  directions   TEXT                             -- วิธีเดินไปห้อง (ต้องเป็นข้อมูลจริงเท่านั้น)
);

-- ------------------------------------------------------------
-- บุคลากร (จากเว็บไซต์ของสาขา)
-- is_public ตามค่าที่ระบบต้นทางกำหนด — ตู้แสดงเฉพาะคนที่เปิดเผยข้อมูลไว้
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS personnel (
  id                       INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id                TEXT UNIQUE,
  prefix                   TEXT,
  fullname_th              TEXT NOT NULL,
  fullname_en              TEXT,
  academic_position        TEXT,
  administrative_position  TEXT,
  personnel_type           TEXT,
  education                TEXT,
  email                    TEXT,
  phone                    TEXT,
  expertise                TEXT,
  work_status              TEXT,
  is_public                INTEGER NOT NULL DEFAULT 0 CHECK (is_public IN (0, 1))
);
CREATE INDEX IF NOT EXISTS ix_personnel_public ON personnel (is_public);

-- ------------------------------------------------------------
-- ตารางเรียน
-- แยก sections / enrollments เพราะคาบเดียวกันมีนักศึกษาหลายคนเรียนร่วมกัน
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sections (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  term_id     INTEGER NOT NULL REFERENCES terms(id)   ON DELETE CASCADE,
  course_id   INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  room_id     INTEGER          REFERENCES rooms(id)   ON DELETE SET NULL,
  day         INTEGER NOT NULL CHECK (day BETWEEN 1 AND 7),   -- 1=จันทร์ ... 7=อาทิตย์
  start_time  TEXT NOT NULL,                    -- 'HH:MM'
  end_time    TEXT NOT NULL,
  teacher     TEXT,
  -- 1 = ข้อมูลสมมติสำหรับสาธิต ยังไม่ได้รับตารางเรียนจริงจากสาขา
  is_synthetic INTEGER NOT NULL DEFAULT 0 CHECK (is_synthetic IN (0, 1)),
  CHECK (start_time < end_time),
  UNIQUE (term_id, course_id, day, start_time)
);

CREATE TABLE IF NOT EXISTS enrollments (
  student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  section_id  INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
  PRIMARY KEY (student_id, section_id)
);

-- กำหนดสอบผูกกับรายวิชา นักศึกษาได้กำหนดสอบจากวิชาที่ลงทะเบียนโดยอัตโนมัติ
CREATE TABLE IF NOT EXISTS exams (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  term_id     INTEGER NOT NULL REFERENCES terms(id)   ON DELETE CASCADE,
  course_id   INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  room_id     INTEGER          REFERENCES rooms(id)   ON DELETE SET NULL,
  exam_type   TEXT NOT NULL,                    -- 'สอบกลางภาค' | 'สอบปลายภาค'
  exam_date   TEXT NOT NULL,                    -- ISO date
  start_time  TEXT NOT NULL,
  end_time    TEXT NOT NULL,
  is_synthetic INTEGER NOT NULL DEFAULT 0 CHECK (is_synthetic IN (0, 1)),
  UNIQUE (term_id, course_id, exam_type)
);

-- ------------------------------------------------------------
-- ตารางสอบจากสำนักบริหารและพัฒนาวิชาการ  (ข้อมูลสาธารณะ ไม่ผูกกับตัวบุคคล)
--
-- แยกจากตาราง exams เดิมซึ่งผูกกับรายวิชาที่นักศึกษาลงทะเบียนไว้
-- ตารางนี้เป็นประกาศของมหาวิทยาลัย ใครก็เปิดดูได้โดยไม่ต้องยืนยันตัวตน
-- นักศึกษาที่ระบบยังไม่มีข้อมูลการลงทะเบียนจึงยังค้นตารางสอบของตัวเองได้
--
-- หนึ่งรายวิชามีได้หลายแถว เพราะแบ่งห้องตามลำดับที่นั่ง
-- การบอกห้องผิดแปลว่านักศึกษาเดินไปผิดห้องสอบ จึงต้องแสดงช่วงที่นั่งกำกับเสมอ
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exam_schedule (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  exam_label     TEXT NOT NULL,              -- 'สอบปลายภาค 1/2569'
  exam_date      TEXT NOT NULL,              -- ISO date
  start_time     TEXT,
  end_time       TEXT,
  course_code    TEXT NOT NULL,
  course_title   TEXT,
  section        INTEGER,
  room           TEXT,
  seats          INTEGER,
  seat_from      INTEGER,
  seat_to        INTEGER,
  source_url     TEXT
);
CREATE INDEX IF NOT EXISTS ix_exam_schedule_code ON exam_schedule (course_code);
CREATE INDEX IF NOT EXISTS ix_exam_schedule_date ON exam_schedule (exam_date);

-- ------------------------------------------------------------
-- ปฏิทินการศึกษา  (ข้อมูลสาธารณะเช่นกัน)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS academic_calendar (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  acadyear_be    INTEGER,
  level          TEXT,
  semester       TEXT,
  event          TEXT NOT NULL,
  start_date     TEXT,                       -- ISO date
  end_date       TEXT,
  note           TEXT,
  source_url     TEXT
);
CREATE INDEX IF NOT EXISTS ix_calendar_start ON academic_calendar (start_date);

-- ------------------------------------------------------------
-- เบอร์ติดต่อหน่วยงานของมหาวิทยาลัย
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS office_contacts (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  department  TEXT NOT NULL,
  service     TEXT,
  phone       TEXT
);

-- ------------------------------------------------------------
-- แบบฟอร์มและเอกสารที่นักศึกษาต้องใช้
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS edu_forms (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  section     TEXT,
  doc_group   TEXT,
  title       TEXT NOT NULL,
  url         TEXT,
  file_type   TEXT,
  -- ในชุดข้อมูลมีเอกสาร 646 ฉบับ แต่ส่วนใหญ่เป็นงานภายในของฝ่ายหลักสูตร
  -- เช่น แบบฟอร์ม มคอ. และเอกสารระบบ CHECO ซึ่งนักศึกษาไม่ได้ใช้เลย
  -- ถ้าค้นรวมกันหมด คำถามอย่าง "ขอใบรับรองทำยังไง" จะได้เอกสารการเงินของเจ้าหน้าที่
  -- จึงทำเครื่องหมายไว้ตั้งแต่ตอนนำเข้า ว่าฉบับไหนเป็นของนักศึกษาจริง ๆ
  for_students INTEGER NOT NULL DEFAULT 0 CHECK (for_students IN (0, 1))
);
CREATE INDEX IF NOT EXISTS ix_forms_title ON edu_forms (title);

-- ------------------------------------------------------------
-- ความยินยอม (พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคลฯ มาตรา 26)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS consents (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id      INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  purpose         TEXT NOT NULL DEFAULT 'face_recognition',
  policy_version  TEXT NOT NULL,                -- ฉบับคำประกาศที่ผู้ใช้เห็นตอนกดยินยอม
  granted_at      TEXT NOT NULL,
  revoked_at      TEXT,                         -- NULL = ยังยินยอมอยู่
  method          TEXT NOT NULL DEFAULT 'kiosk_touch'
);
CREATE INDEX IF NOT EXISTS ix_consents_student ON consents (student_id, purpose);

-- ------------------------------------------------------------
-- เวกเตอร์ใบหน้า  (ไม่เก็บภาพ เก็บเฉพาะค่าเวกเตอร์)
-- consent_id เป็น NOT NULL → ไม่มีความยินยอม = เขียนลงตารางนี้ไม่ได้
-- ON DELETE CASCADE → ลบ consent ทิ้ง เวกเตอร์หายตามทันที
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS face_embeddings (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  consent_id  INTEGER NOT NULL REFERENCES consents(id) ON DELETE CASCADE,
  vector      BLOB    NOT NULL,                 -- float32 little-endian, L2-normalised
  dim         INTEGER NOT NULL,
  model       TEXT    NOT NULL,                 -- เช่น 'buffalo_s/w600k_mbf'
  quality     REAL,
  created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_face_student ON face_embeddings (student_id);

-- กันการเขียนเวกเตอร์ทับความยินยอมที่ถอนไปแล้ว หรือของนักศึกษาคนอื่น
CREATE TRIGGER IF NOT EXISTS trg_face_requires_live_consent
BEFORE INSERT ON face_embeddings
FOR EACH ROW
BEGIN
  SELECT RAISE(ABORT, 'ความยินยอมไม่ถูกต้องหรือถูกถอนแล้ว')
  WHERE NOT EXISTS (
    SELECT 1 FROM consents c
    WHERE c.id = NEW.consent_id
      AND c.student_id = NEW.student_id
      AND c.purpose = 'face_recognition'
      AND c.revoked_at IS NULL
  );
END;

-- ------------------------------------------------------------
-- คำถามยอดนิยม (ปุ่มแตะบนหน้าผู้ช่วย)
--   source: 'db'   = ตอบจากฐานข้อมูลโดยตรง ไม่ผ่าน AI ใช้ได้ตอนออฟไลน์
--           'ai'   = ส่งให้ผู้ช่วย AI ต้องมีเอกสารอ้างอิงเสมอ
--           'none' = ไม่มีข้อมูลในระบบ ห้ามเดาคำตอบ
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quick_questions (
  id          TEXT PRIMARY KEY,
  label       TEXT NOT NULL,
  kind        TEXT NOT NULL,                    -- ประเภทคำถาม ใช้เป็นมิติของสถิติ
  source      TEXT NOT NULL CHECK (source IN ('db', 'ai', 'none')),
  personal    INTEGER NOT NULL DEFAULT 0 CHECK (personal IN (0, 1)),
  sort_order  INTEGER NOT NULL DEFAULT 0,
  active      INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

-- ------------------------------------------------------------
-- คลังเอกสารสำหรับผู้ช่วย AI (RAG)
-- ทุกคำตอบของ AI ต้องชี้กลับมาที่ documents.citation_label ได้เสมอ
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  title           TEXT NOT NULL,
  citation_label  TEXT NOT NULL,                -- ข้อความที่แสดงบนป้าย "อ้างอิง: ..."
  source_path     TEXT,
  effective_date  TEXT,
  created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS doc_chunks (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  ordinal      INTEGER NOT NULL,
  page         TEXT,                            -- 'หน้า 18' หรือหัวข้อของชิ้นเอกสาร
  content      TEXT NOT NULL,
  source_url   TEXT,
  source_id    TEXT,                            -- id เดิมจากชุดข้อมูลต้นทาง
  UNIQUE (document_id, ordinal)
);

-- trigram tokenizer ค้นภาษาไทยได้โดยไม่ต้องตัดคำ (ไทยไม่เว้นวรรคระหว่างคำ)
CREATE VIRTUAL TABLE IF NOT EXISTS doc_chunks_fts USING fts5 (
  content,
  content = 'doc_chunks',
  content_rowid = 'id',
  tokenize = 'trigram'
);

CREATE TRIGGER IF NOT EXISTS trg_doc_chunks_ai AFTER INSERT ON doc_chunks BEGIN
  INSERT INTO doc_chunks_fts (rowid, content) VALUES (NEW.id, NEW.content);
END;
CREATE TRIGGER IF NOT EXISTS trg_doc_chunks_ad AFTER DELETE ON doc_chunks BEGIN
  INSERT INTO doc_chunks_fts (doc_chunks_fts, rowid, content) VALUES ('delete', OLD.id, OLD.content);
END;
CREATE TRIGGER IF NOT EXISTS trg_doc_chunks_au AFTER UPDATE ON doc_chunks BEGIN
  INSERT INTO doc_chunks_fts (doc_chunks_fts, rowid, content) VALUES ('delete', OLD.id, OLD.content);
  INSERT INTO doc_chunks_fts (rowid, content) VALUES (NEW.id, NEW.content);
END;

-- ------------------------------------------------------------
-- สถิติการใช้งาน  (ไม่มีข้อมูลระบุตัวตนโดยเจตนา — ไม่มี FK ไป students)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usage_events (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at    TEXT NOT NULL,
  question_kind  TEXT,
  channel        TEXT    CHECK (channel IN ('เสียง', 'แตะ', 'พิมพ์')),
  answer_source  TEXT    CHECK (answer_source IN ('ฐานข้อมูล', 'AI', 'ไม่พบ')),
  latency_ms     INTEGER
);
CREATE INDEX IF NOT EXISTS ix_usage_time ON usage_events (occurred_at);
