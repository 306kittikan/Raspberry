# ติดตั้งลง Raspberry Pi 5

คู่มือนี้พาติดตั้งตู้บริการข้อมูลจากเครื่องเปล่าจนเปิดให้บริการได้
เขียนให้คนที่ไม่เคยแตะโปรเจกต์นี้มาก่อนทำตามได้ทีละขั้น

ทุกคำสั่งในคู่มือนี้รันบน Raspberry Pi เว้นแต่จะเขียนกำกับว่า **บนเครื่องพัฒนา**

---

## ภาพรวม

ตู้ทำงานด้วยโปรเซสเดียวและพอร์ตเดียว

```
Chromium (เต็มจอ) ──► http://127.0.0.1:8000
                            │
                     uvicorn + FastAPI
                       ├─ เสิร์ฟหน้าเว็บจาก web/dist
                       ├─ API และ WebSocket
                       ├─ เธรดกล้อง → รู้จำใบหน้า
                       └─ ถอดเสียงภาษาไทย (ทำงานในเครื่อง)
                            │
                       SQLite (server/data/kiosk.db)
```

เซิร์ฟเวอร์เสิร์ฟทั้งหน้าเว็บและ API จาก origin เดียวกัน จึงไม่มีเรื่อง CORS
และไม่ต้องติดตั้ง nginx

**สิ่งที่ทำงานได้แม้ไม่มีอินเทอร์เน็ต** — ตารางเรียน ห้องเรียน กำหนดสอบ
ข้อมูลอาจารย์ ปฏิทินการศึกษา รู้จำใบหน้า และถอดเสียง
มีเพียงคำถามปลายเปิดที่ต้องใช้ผู้ช่วย AI เท่านั้นที่ต้องต่อเน็ต

---

## 1. ของที่ต้องมี

| | ขั้นต่ำ | แนะนำ | หมายเหตุ |
| --- | --- | --- | --- |
| บอร์ด | Pi 5 · 4 GB | **Pi 5 · 8 GB** | 4 GB ใช้ได้แต่ต้องลดโมเดลถอดเสียงเป็น `base` |
| ที่เก็บข้อมูล | microSD 32 GB | **SSD ผ่าน USB 3.0** | โมเดลกับฐานข้อมูลรวมราว 1 GB · SSD บูตเร็วกว่าและทนกว่ามาก |
| จอ | 1080×1920 สัมผัส | เท่าเดิม | ตู้ออกแบบมาเป็นแนวตั้ง |
| กล้อง | USB webcam | **Pi Camera Module 3** | ทั้งสองแบบใช้ได้ ดูข้อ 4.3 |
| ไมโครโฟน | ในตัวของ webcam | **ไมค์แยกแบบ USB** | ความแม่นของการถอดเสียงขึ้นกับไมค์มากกว่าโมเดล |
| ไฟเลี้ยง | อะแดปเตอร์แท้ 27 W | เท่าเดิม | ไฟไม่พอทำให้บอร์ดลดความเร็วลงเงียบ ๆ แล้วตู้ช้าโดยไม่มีสาเหตุ |
| ระบบปฏิบัติการ | Raspberry Pi OS **64-bit** | Bookworm หรือใหม่กว่า | **32-bit ใช้ไม่ได้** เพราะไม่มี wheel ของ onnxruntime |

> ตรวจว่าเป็น 64-bit จริง — `uname -m` ต้องได้ `aarch64`
> ถ้าได้ `armv7l` แปลว่าลง OS ผิดรุ่น ต้องลงใหม่

---

## 2. เตรียมระบบปฏิบัติการ

### 2.1 สร้างผู้ใช้สำหรับตู้

ไฟล์ตั้งค่าที่เตรียมไว้อ้างถึงผู้ใช้ชื่อ `kiosk` และโฟลเดอร์ `/home/kiosk/Raspberry`
ถ้าใช้ชื่ออื่นต้องแก้ไฟล์ใน `deploy/` ตามไปด้วย

```bash
sudo adduser kiosk
sudo usermod -aG video,audio,gpio kiosk   # video = เข้าถึงกล้อง, audio = ไมโครโฟน
```

### 2.2 เขตเวลาและภาษา

```bash
sudo timedatectl set-timezone Asia/Bangkok
sudo raspi-config nonint do_change_locale th_TH.UTF-8
```

ตู้บังคับใช้เวลาไทยในโค้ดอยู่แล้ว (`KIOSK_TZ`) แต่ตั้งที่ระบบด้วย
จะทำให้บันทึกการทำงานอ่านง่ายตอนไล่ปัญหา

### 2.3 ติดตั้งแพ็กเกจของระบบ

```bash
sudo apt update && sudo apt full-upgrade -y

sudo apt install -y \
  python3 python3-venv python3-dev python3-pip \
  git curl \
  libatlas-base-dev libopenblas-dev \
  libgl1 libglib2.0-0 \
  ffmpeg \
  chromium-browser \
  unclutter xdotool x11-xserver-utils

# เฉพาะเมื่อใช้ Pi Camera Module (ไม่ใช่ USB webcam)
sudo apt install -y python3-picamera2
```

ทำไมต้องมีแต่ละตัว

- `libopenblas-dev` — numpy ใช้คำนวณเวกเตอร์ใบหน้า
- `libgl1 libglib2.0-0` — OpenCV ต้องใช้แม้จะไม่เปิดหน้าต่างภาพ
- `ffmpeg` — เผื่อ PyAV ต้องใช้ตัวถอดรหัสของระบบ
- `unclutter` — ซ่อนเคอร์เซอร์เมาส์ ตู้สัมผัสไม่ควรมีลูกศรค้างอยู่กลางจอ
- `x11-xserver-utils` — มีคำสั่ง `xset` ไว้ปิดการดับจอ

### 2.4 ติดตั้ง Node.js (เฉพาะกรณี build หน้าเว็บบน Pi)

ถ้า build บนเครื่องพัฒนาแล้วคัดลอก `web/dist` มา **ข้ามข้อนี้ได้**
วิธีนั้นเร็วกว่ามากและแนะนำให้ทำแบบนั้น

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

---

## 3. นำโค้ดและข้อมูลขึ้นเครื่อง

### 3.1 โคลนโปรเจกต์

```bash
sudo -iu kiosk
git clone <ที่อยู่ repo> ~/Raspberry
cd ~/Raspberry
```

### 3.2 ไฟล์ที่ git ไม่มี ต้องคัดลอกด้วยมือ

นี่คือขั้นที่คนลืมบ่อยที่สุด ไฟล์เหล่านี้ถูกกันไว้ใน `.gitignore` โดยตั้งใจ
เพราะเป็นข้อมูลส่วนบุคคลจริง ความลับ หรือไฟล์ใหญ่

| สิ่งที่ต้องคัดลอก | ขนาด | ถ้าไม่มีจะเป็นอย่างไร |
| --- | --- | --- |
| `server/.env` | เล็ก | เซิร์ฟเวอร์ใช้ค่าปริยายทั้งหมด · **ไม่มีกุญแจ AI** · โหมดจำลองเปิดค้าง |
| `server/models/` | ~605 MB | ปุ่มไมโครโฟนใช้ไม่ได้ |
| `~/.insightface/` | ~281 MB | สแกนใบหน้าใช้ไม่ได้ |
| `server/data/kiosk.db` | ~5 MB | ตู้ว่างเปล่า ไม่มีข้อมูลอะไรเลย |
| `web/dist/` | ~264 KB | ไม่มีหน้าจอให้เสิร์ฟ |
| `csmju_dataset/my_semester_*/` | เล็ก | ตารางเรียนรายบุคคลหายไป |

**บนเครื่องพัฒนา** — ส่งทั้งหมดในคำสั่งเดียว

```bash
cd d:/smartscreen/Raspberry

scp server/.env            kiosk@<ไอพีของ Pi>:~/Raspberry/server/
scp -r server/models       kiosk@<ไอพีของ Pi>:~/Raspberry/server/
scp -r server/data         kiosk@<ไอพีของ Pi>:~/Raspberry/server/
scp -r web/dist            kiosk@<ไอพีของ Pi>:~/Raspberry/web/
scp -r ~/.insightface      kiosk@<ไอพีของ Pi>:~/
scp -r csmju_dataset/my_semester_1-2569 kiosk@<ไอพีของ Pi>:~/Raspberry/csmju_dataset/
```

> **ไฟล์ตารางเรียนรายบุคคลและฐานข้อมูลมีข้อมูลนักศึกษาจริง**
> รวมถึงเวกเตอร์ใบหน้าซึ่งเป็นข้อมูลชีวภาพตาม พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคลฯ มาตรา 26
> ส่งผ่าน `scp` ในวงแลนที่เชื่อถือได้เท่านั้น อย่าส่งผ่านแชทหรืออีเมล
> และอย่าเก็บสำเนาทิ้งไว้บนเครื่องที่คนอื่นเข้าถึงได้

ถ้าไม่อยากคัดลอกฐานข้อมูล จะสร้างใหม่บน Pi ก็ได้ (ดูข้อ 4.4)
แต่ข้อมูลใบหน้าที่ลงทะเบียนไว้แล้วจะไม่ตามไปด้วย ซึ่งถูกต้องตามหลักความเป็นส่วนตัว

---

## 4. ติดตั้งฝั่งเซิร์ฟเวอร์

### 4.1 สร้างสภาพแวดล้อม Python

```bash
cd ~/Raspberry/server

# --system-site-packages จำเป็นเมื่อใช้ Pi Camera Module
# เพราะ picamera2 ติดตั้งผ่าน apt ลงใน Python ของระบบ ไม่ใช่ใน venv
python3 -m venv .venv --system-site-packages

.venv/bin/pip install --upgrade pip wheel
```

### 4.2 ติดตั้งไลบรารี

```bash
.venv/bin/pip install -r requirements.txt
```

ขั้นนี้ใช้เวลาราว 10–20 นาทีบน Pi เพราะบางตัวต้องคอมไพล์

**ถ้าติดตั้ง `opencv-python` ไม่ผ่านหรือนานเกินไป** ให้ใช้รุ่นไม่มีส่วนติดต่อผู้ใช้แทน
ตู้ไม่เคยเปิดหน้าต่างภาพอยู่แล้ว

```bash
.venv/bin/pip install opencv-python-headless
```

**ถ้า `onnxruntime` หา wheel ไม่เจอ** แปลว่ารุ่น Python บนเครื่องใหม่หรือเก่าเกินไป
ตรวจด้วย `python3 -V` แล้วเทียบกับที่ `pip` แจ้ง
ทางแก้ที่ตรงที่สุดคือใช้ Raspberry Pi OS รุ่นที่มาพร้อม Python 3.11 หรือ 3.12

ตรวจว่าติดตั้งครบ

```bash
.venv/bin/python -c "
import numpy, cv2, onnxruntime, insightface, faster_whisper
print('ไลบรารีครบ')
"
```

### 4.3 ตั้งค่ากล้อง

**Pi Camera Module** — เปิดใช้งานก่อน

```bash
sudo raspi-config nonint do_camera 0
sudo reboot
# หลังบูต ตรวจว่าเห็นกล้อง
libcamera-hello --list-cameras
```

**USB webcam** — เสียบแล้วตรวจ

```bash
ls /dev/video*
v4l2-ctl --list-devices     # ถ้ายังไม่มีคำสั่ง: sudo apt install v4l-utils
```

แล้วตั้งค่าใน `server/.env`

```bash
KIOSK_CAMERA=auto        # ลอง Pi Camera ก่อน ไม่มีค่อยใช้ USB ตัวแรก
# KIOSK_CAMERA=picamera  # บังคับใช้ Pi Camera
# KIOSK_CAMERA=0         # บังคับใช้ /dev/video0
# KIOSK_CAMERA=off       # ปิดกล้อง เหลือแต่การกรอกรหัสนักศึกษา
```

### 4.4 เตรียมฐานข้อมูล (เฉพาะกรณีไม่ได้คัดลอกมา)

```bash
cd ~/Raspberry/server

.venv/bin/python -m app.seed                                   # สร้างตารางและข้อมูลตั้งต้น
.venv/bin/python -m app.import_csmju --dataset ../csmju_dataset/csmju_datasev3
.venv/bin/python scripts/import_timetable.py ../csmju_dataset/csmju_timetable_dataset
.venv/bin/python scripts/import_roster.py <ไฟล์รายชื่อ>        # ถ้ามีรายชื่อจากระบบทะเบียน
.venv/bin/python scripts/import_my_semester.py ../csmju_dataset/my_semester_1-2569
```

### 4.5 เตรียมโมเดลถอดเสียง (เฉพาะกรณีไม่ได้คัดลอกมา)

ต้องทำตอนที่ยังต่อเน็ตอยู่ เพราะตู้จริงจะถูกตั้งให้ห้ามดาวน์โหลด

```bash
cd ~/Raspberry/server
KIOSK_STT_OFFLINE_ONLY=0 .venv/bin/python -c "
from faster_whisper import WhisperModel
from app import config
WhisperModel(config.STT_MODEL, device='cpu', compute_type='int8',
             download_root=str(config.STT_MODEL_DIR))
print('โหลดโมเดลเรียบร้อย')
"
```

---

## 5. หน้าเว็บ

**วิธีที่แนะนำ — build บนเครื่องพัฒนา** แล้วคัดลอก `web/dist` มา (ข้อ 3.2)

**ถ้าจะ build บน Pi**

```bash
cd ~/Raspberry/web
npm ci
npm run build
```

### 5.1 ฟอนต์ กับการทำงานขณะออฟไลน์

ตอนนี้ `web/index.html` โหลดฟอนต์ไทยจาก Google Fonts
**ถ้าตู้ไม่มีเน็ต ตัวอักษรจะกลายเป็นฟอนต์สำรองของระบบ** ซึ่งอ่านยากบนจอใหญ่

ถ้าตู้ต้องทำงานออฟไลน์ ให้ดาวน์โหลดฟอนต์มาเก็บในโปรเจกต์

```bash
cd ~/Raspberry/web
mkdir -p public/fonts
# ดาวน์โหลด IBM Plex Sans Thai และ Noto Sans Thai (.woff2) มาไว้ที่ public/fonts/
# แล้วแก้ index.html จาก <link href="https://fonts.googleapis.com/..."> เป็น @font-face ที่ชี้มาที่ /fonts/
npm run build
```

ข้อนี้ยังไม่ได้ทำในโปรเจกต์ ถ้าตู้ต่อเน็ตตลอดเวลาก็ข้ามได้

---

## 6. ตั้งค่าสำหรับตู้จริง

แก้ `server/.env` ค่าที่ **ต้องเปลี่ยน** ก่อนเปิดบริการ

```bash
# ============ บังคับ ============
KIOSK_SIM=0                    # ห้ามเป็น 1 เด็ดขาด — ดูคำอธิบายข้างล่าง
KIOSK_STT_OFFLINE_ONLY=1       # ห้ามดาวน์โหลดโมเดลระหว่างให้บริการ

# ============ ควรตรวจ ============
KIOSK_TZ=Asia/Bangkok
KIOSK_CAMERA=auto
KIOSK_KEYPAD_RESTRICTED=1      # โหมดกรอกรหัสไม่ยืนยันตัวตน จึงต้องจำกัดสิทธิ

# ============ ผู้ช่วย AI ============
GEMINI_API_KEY=...             # หรือ ANTHROPIC_API_KEY
KIOSK_AI_TIMEOUT=20
KIOSK_AI_RETRIES=1

# ============ ปรับตามเครื่อง ============
KIOSK_STT_MODEL=small          # ลดเป็น base ถ้าเป็น Pi รุ่น 4 GB หรือช้าเกินไป
KIOSK_STT_BEAM=5               # ลดเป็น 3 ถ้าต้องการให้เร็วขึ้น
```

แล้วรัดกุมสิทธิ์ไฟล์ เพราะมีกุญแจ API อยู่ข้างใน

```bash
chmod 600 server/.env
```

> ### ทำไม `KIOSK_SIM=0` ถึงสำคัญที่สุด
>
> เมื่อเปิดโหมดจำลอง เส้นทาง `/api/sim/*` จะเปิดใช้งาน
> ซึ่งรวมถึง `/api/sim/face/recognized` ที่สร้างผลการรู้จำใบหน้าให้ **นักศึกษาคนใดก็ได้**
> โดยไม่ต้องมีใบหน้าจริง
>
> แปลว่าใครก็ตามที่เข้าถึงเครื่องได้ จะดูตารางเรียนของคนอื่นได้ทันที
> และ `/api/sim/students` ยังคืนรายชื่อพร้อมรหัสนักศึกษาทั้งหมดอีกด้วย

---

## 7. ทดสอบก่อนทำเป็นบริการ

อย่าเพิ่งตั้ง systemd จนกว่าจะรันด้วยมือแล้วผ่าน

```bash
cd ~/Raspberry/server
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

เปิดอีกหน้าต่างแล้วตรวจ

```bash
curl -s http://127.0.0.1:8000/api/health      | python3 -m json.tool
curl -s http://127.0.0.1:8000/api/face/status | python3 -m json.tool
curl -s http://127.0.0.1:8000/api/voice/status | python3 -m json.tool
curl -s http://127.0.0.1:8000/api/ai/status   | python3 -m json.tool
```

สิ่งที่ต้องเห็น

| เส้นทาง | ค่าที่ถูกต้อง |
| --- | --- |
| `/api/health` | `"ok": true` และ `"term"` ไม่เป็น null |
| `/api/face/status` | `"running": true` · `"modelReady": true` · `camera.available: true` |
| `/api/voice/status` | `"ready": true` |
| `/api/ai/status` | `"enabled": true` และ `"failures": 0` |

แล้วรันชุดทดสอบทั้งหมด

```bash
cd ~/Raspberry/server
.venv/bin/python scripts/usecases.py        # กรณีการใช้งาน
.venv/bin/python scripts/smoke.py           # API
.venv/bin/python scripts/test_assistant_ai.py
```

สุดท้ายรันตัวตรวจความพร้อม

```bash
cd ~/Raspberry
bash deploy/preflight.sh
```

ตัวนี้ตรวจเฉพาะสิ่งที่ผิดแล้วเห็นผลตอนมีคนมายืนหน้าตู้
ถ้ามีข้อที่ขึ้นว่า `[ตก]` **ห้ามเปิดบริการ**

---

## 8. ทำให้ขึ้นเองตอนบูต

### 8.1 เซิร์ฟเวอร์

```bash
sudo cp ~/Raspberry/deploy/kiosk-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kiosk-api

systemctl status kiosk-api
journalctl -u kiosk-api -f        # ดูบันทึกสด
```

> ถ้าใช้ชื่อผู้ใช้หรือเส้นทางอื่น ต้องแก้ `User=` `Group=` `WorkingDirectory=`
> และ `ExecStart=` ในไฟล์ service ก่อนคัดลอก

### 8.2 เบราว์เซอร์

```bash
mkdir -p ~/.config/systemd/user
cp ~/Raspberry/deploy/kiosk-browser.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now kiosk-browser

# ให้เปิดเองตอนบูตโดยไม่ต้องมีคนล็อกอิน
sudo loginctl enable-linger kiosk
```

บริการเบราว์เซอร์จะรอจนกว่า `/api/health` ตอบก่อนค่อยเปิดหน้าจอ
ผู้ใช้จึงไม่เห็นหน้า "ต่อเซิร์ฟเวอร์ไม่ได้" ค้างอยู่ตอนบูต

### 8.3 ปิดการดับจอและซ่อนเคอร์เซอร์

สร้าง `~/.config/autostart/kiosk-display.desktop`

```ini
[Desktop Entry]
Type=Application
Name=ตั้งค่าจอของตู้
Exec=/home/kiosk/Raspberry/deploy/display-setup.sh
X-GNOME-Autostart-enabled=true
```

แล้วสร้าง `deploy/display-setup.sh`

```bash
#!/usr/bin/env bash
# ปิดการดับจอ ตู้ต้องสว่างตลอดเวลาทำการ
xset s off
xset -dpms
xset s noblank
# ซ่อนเคอร์เซอร์เมาส์หลังไม่ขยับ 0.5 วินาที
unclutter -idle 0.5 -root &
```

```bash
chmod +x ~/Raspberry/deploy/display-setup.sh
```

### 8.4 หมุนจอเป็นแนวตั้ง

ขึ้นกับว่าใช้ระบบหน้าต่างแบบไหน ตรวจด้วย `echo $XDG_SESSION_TYPE`

**Wayland (ค่าปริยายของ Bookworm)** — แก้ `~/.config/wayfire.ini`

```ini
[output:HDMI-A-1]
mode = 1080x1920@60
transform = 90
```

**X11** — เพิ่มใน `display-setup.sh`

```bash
xrandr --output HDMI-1 --rotate left
```

ชื่อเอาต์พุตอาจไม่ตรง ตรวจด้วย `xrandr --query` หรือ `wlr-randr`

> หน้าจอออกแบบมาที่ 1080×1920 และย่อให้พอดีจอเองอัตโนมัติ
> ถ้าจอมีขนาดอื่นก็ยังใช้ได้ แต่จะมีขอบดำ

---

## 9. ตรวจหลังติดตั้ง

ทำรายการนี้ให้ครบก่อนส่งมอบ

- [ ] รีบูตเครื่อง แล้วตู้ขึ้นหน้าจอเองโดยไม่ต้องแตะอะไร
- [ ] `bash deploy/preflight.sh` ไม่มีข้อที่ขึ้นว่า `[ตก]`
- [ ] แตะ "เริ่มสแกนใบหน้า" แล้วเห็นภาพสดจากกล้อง
- [ ] ลงทะเบียนใบหน้าหนึ่งคน แล้วสแกนใหม่ จำได้ภายในไม่กี่วินาที
- [ ] กดปุ่มไมโครโฟนแล้วพูด เห็นข้อความที่ระบบได้ยิน
- [ ] ถามคำถามปลายเปิด ได้คำตอบพร้อมป้ายบอกที่มา
- [ ] ถอดสายแลนหรือปิด Wi-Fi แล้วตารางเรียนยังดูได้ · คำถาม AI ขึ้นว่าออฟไลน์
- [ ] ยืนเฉย ๆ 30 วินาที แล้วตู้ออกจากระบบเองและล้างข้อมูลบนจอ
- [ ] ดึงปลั๊กแล้วเสียบใหม่ ตู้กลับมาเองภายใน 2 นาที
- [ ] `journalctl -u kiosk-api --since "10 min ago"` ไม่มีข้อผิดพลาดซ้ำ ๆ

---

## 10. ปัญหาที่พบบ่อย

### ตู้ขึ้น "กล้องใช้งานไม่ได้"

```bash
curl -s http://127.0.0.1:8000/api/face/status | python3 -m json.tool
```

ดูที่ `downReason` และ `camera.error`

| อาการ | สาเหตุที่พบบ่อย |
| --- | --- |
| `Permission denied` | ผู้ใช้ `kiosk` ไม่ได้อยู่กลุ่ม `video` → `sudo usermod -aG video kiosk` แล้วรีบูต |
| `ไม่พบกล้อง` | สาย USB หลวม หรือยังไม่ได้เปิด Pi Camera ใน `raspi-config` |
| `Arena alloc failed` | หน่วยความจำไม่พอ → ลด `KIOSK_STT_MODEL` เป็น `base` |
| ค้างอยู่ครู่เดียวแล้วหาย | ปกติ — ตู้พยายามกู้กล้องเองทุก 15 วินาที |

### ถอดเสียงเพี้ยนมาก

เรียงตามผลที่ได้จากมากไปน้อย

1. **ไมโครโฟน** — ไมค์ในตัวของ webcam ที่อยู่ห่าง 60 ซม. คือสาเหตุอันดับหนึ่ง
   ไมค์ USB แบบตั้งโต๊ะช่วยได้มากกว่าการเปลี่ยนโมเดลทุกรุ่นรวมกัน
2. `KIOSK_STT_MODEL=medium` — แม่นขึ้นแต่ช้าลงราวสองเท่า
3. `KIOSK_STT_VOCAB=1` — ลองเปิดเทียบดู ช่วยกับชื่ออาจารย์และชื่ออาคาร

ตรวจว่าระบบได้ยินอะไร

```bash
arecord -l                                    # ไมค์ที่เครื่องเห็น
arecord -d 5 -f cd /tmp/test.wav && aplay /tmp/test.wav
```

### ปุ่มไมโครโฟนกดไม่ได้เลย

เบราว์เซอร์ให้ใช้ไมโครโฟนเฉพาะ `https` หรือ `localhost`
ไฟล์ `kiosk-browser.service` ใส่ `--unsafely-treat-insecure-origin-as-secure` ไว้แล้ว
ถ้าเปิดเบราว์เซอร์เองด้วยมือต้องใส่ตัวเลือกนี้ด้วย

**และถ้าเปิดตู้จากเครื่องอื่นผ่านวงแลน ไมโครโฟนจะใช้ไม่ได้เสมอ**
เพราะ `http://192.168.x.x` ไม่นับเป็นต้นทางปลอดภัย

### ตู้ช้าลงเรื่อย ๆ

```bash
vcgencmd measure_temp          # เกิน 80°C แปลว่าร้อนจนลดความเร็ว
vcgencmd get_throttled         # ไม่ใช่ 0x0 แปลว่าไฟไม่พอหรือร้อนเกิน
free -h
```

`throttled` ที่ไม่ใช่ `0x0` มักแปลว่าใช้อะแดปเตอร์ไม่ถึง 27 W

### หน้าจอขาวเปล่า

```bash
ls ~/Raspberry/web/dist/index.html    # มีไฟล์ไหม
journalctl -u kiosk-api --since "5 min ago" | tail -30
```

ถ้าไม่มี `web/dist` เซิร์ฟเวอร์จะตอบเฉพาะ API และไม่มีหน้าจอให้เสิร์ฟ

---

## 11. การดูแลต่อเนื่อง

### สำรองข้อมูล

```bash
sudo systemctl stop kiosk-api
cp ~/Raspberry/server/data/kiosk.db ~/backup/kiosk-$(date +%F).db
sudo systemctl start kiosk-api
```

หยุดบริการก่อนคัดลอกเสมอ ไม่งั้นอาจได้ไฟล์ที่เขียนค้างอยู่

> ไฟล์สำรองมีเวกเตอร์ใบหน้าอยู่ข้างใน ซึ่งเป็นข้อมูลชีวภาพ
> เก็บในที่ที่ควบคุมการเข้าถึงได้ และลบเมื่อไม่ต้องใช้แล้ว

### อัปเดตโค้ด

```bash
cd ~/Raspberry
git pull
cd server && .venv/bin/pip install -r requirements.txt
cd ../web && npm ci && npm run build          # หรือคัดลอก dist ที่ build มาแล้ว
sudo systemctl restart kiosk-api
systemctl --user restart kiosk-browser
bash ~/Raspberry/deploy/preflight.sh
```

### จัดการข้อมูลใบหน้าตามคำขอของเจ้าของข้อมูล

```bash
cd ~/Raspberry/server
.venv/bin/python scripts/students.py --registry            # ใครมีข้อมูลในระบบบ้าง
.venv/bin/python scripts/students.py --show 6604101xxx     # ดูข้อมูลของคนหนึ่งคน
.venv/bin/python scripts/students.py --export 6604101xxx   # ส่งออกให้เจ้าตัว
.venv/bin/python scripts/students.py --forget 6604101xxx   # ลบข้อมูลใบหน้า
.venv/bin/python scripts/students.py --cleanup-consents    # เก็บความยินยอมที่ค้าง
```

จำเป็นต้องมีช่องทางนี้ เพราะการลบผ่านหน้าตู้ต้องยืนยันตัวตนด้วยใบหน้าก่อน
ถ้าระบบจำหน้าเจ้าของข้อมูลไม่ได้ เขาจะลบข้อมูลตัวเองไม่ได้เลย

---

## 12. สิ่งที่ยังไม่ได้ทำ

บอกไว้ตามตรงเพื่อให้ตัดสินใจได้ว่าพร้อมส่งมอบจริงหรือยัง

- **ยังไม่เคยติดตั้งบน Pi จริง** — ตัวเลขความเร็วทั้งหมดในโปรเจกต์วัดจากโน้ตบุ๊ก
  ขั้นที่น่าจะติดปัญหาที่สุดคือการติดตั้ง `onnxruntime` และ `opencv-python`
- **ฟอนต์ยังโหลดจาก Google Fonts** — ตู้ที่ไม่มีเน็ตจะได้ฟอนต์สำรองของระบบ (ข้อ 5.1)
- **ไม่มีระบบยืนยันตัวตนของเจ้าหน้าที่** — เครื่องมือจัดการข้อมูลจึงเป็นสคริปต์
  ที่ต้องรันบนเครื่อง ไม่ใช่หน้าเว็บ ใครเข้าถึงเครื่องได้คือเข้าถึงข้อมูลได้
- **ยังไม่ได้วัดความแม่นของการถอดเสียงกับผู้พูดจริงหลายคน**
- **ตารางเรียนมีเฉพาะคนที่นำเข้าข้อมูลไว้** คนอื่นจะเห็นข้อความว่ายังไม่มีข้อมูล
  ซึ่งถูกต้องกว่าการแสดงตารางของคนอื่น

---

## ภาคผนวก · คำสั่งที่ใช้บ่อย

```bash
# สถานะและบันทึก
systemctl status kiosk-api
journalctl -u kiosk-api -f
journalctl -u kiosk-api --since today | grep -i error

# เริ่มใหม่
sudo systemctl restart kiosk-api
systemctl --user restart kiosk-browser

# หยุดชั่วคราวเพื่อซ่อมบำรุง
sudo systemctl stop kiosk-api kiosk-browser

# ดูสถานะทุกระบบในคำสั่งเดียว
for p in health face/status voice/status ai/status; do
  echo "--- $p ---"
  curl -s "http://127.0.0.1:8000/api/$p" | python3 -m json.tool
done
```
