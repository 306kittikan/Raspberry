#!/usr/bin/env bash
# ตรวจความพร้อมก่อนเปิดตู้ให้บริการจริง
#
#   bash deploy/preflight.sh
#
# ตรวจเฉพาะสิ่งที่ "ผิดแล้วเห็นผลตอนมีคนมายืนหน้าตู้" เท่านั้น
# ไม่ใช่รายการสิ่งที่ควรทำทั่วไป
#
# ออกด้วยรหัส 1 ถ้ามีข้อที่ต้องแก้ก่อนเปิดบริการ

set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

PASS=0
WARN=0
FAIL=0

ok()   { echo "  [ผ่าน]  $1"; PASS=$((PASS+1)); }
warn() { echo "  [เตือน] $1"; WARN=$((WARN+1)); }
bad()  { echo "  [ตก]    $1"; FAIL=$((FAIL+1)); }

echo "ตรวจความพร้อมของตู้"
echo

# ------------------------------------------------------------
echo "1. ความปลอดภัย"

if [ ! -f server/.env ]; then
  bad "ไม่มีไฟล์ server/.env — คัดลอกจาก .env.example แล้วแก้ค่า"
else
  SIM=$(grep -E '^KIOSK_SIM=' server/.env | tail -1 | cut -d= -f2 | tr -d '[:space:]')
  if [ "$SIM" = "0" ]; then
    ok "โหมดจำลองปิดอยู่ (KIOSK_SIM=0)"
  else
    bad "โหมดจำลองยังเปิดอยู่ — ใครก็สวมรอยเป็นนักศึกษาคนไหนก็ได้ผ่าน /api/sim/*"
  fi

  if grep -qE '^(GEMINI_API_KEY|ANTHROPIC_API_KEY)=.+' server/.env; then
    ok "มีกุญแจผู้ช่วย AI"
  else
    warn "ไม่มีกุญแจ AI — คำถามปลายเปิดจะตอบว่าไม่พบข้อมูล ส่วนตารางเรียนยังใช้ได้"
  fi

  PERM=$(stat -c '%a' server/.env 2>/dev/null || echo '?')
  if [ "$PERM" = "600" ] || [ "$PERM" = "400" ]; then
    ok "สิทธิ์ไฟล์ .env รัดกุม ($PERM)"
  else
    warn "สิทธิ์ไฟล์ .env คือ $PERM — มีกุญแจ API อยู่ ควรตั้ง chmod 600"
  fi
fi

# ------------------------------------------------------------
echo
echo "2. ข้อมูลและโมเดล"

if [ -f server/data/kiosk.db ]; then
  ok "มีฐานข้อมูล ($(du -h server/data/kiosk.db | cut -f1))"
else
  bad "ไม่มี server/data/kiosk.db — ตู้จะไม่มีข้อมูลอะไรเลย"
fi

if [ -d web/dist ] && [ -f web/dist/index.html ]; then
  ok "มีหน้าเว็บที่ build แล้ว"
else
  bad "ไม่มี web/dist — เซิร์ฟเวอร์จะไม่มีหน้าจอให้เสิร์ฟ"
fi

if [ -d server/models/whisper ] && [ -n "$(ls -A server/models/whisper 2>/dev/null)" ]; then
  ok "มีโมเดลถอดเสียง ($(du -sh server/models/whisper | cut -f1))"
else
  warn "ไม่มีโมเดลถอดเสียง — ปุ่มไมโครโฟนจะใช้ไม่ได้"
fi

if [ -d ~/.insightface ]; then
  ok "มีโมเดลรู้จำใบหน้า"
else
  warn "ไม่มีโมเดลรู้จำใบหน้าที่ ~/.insightface — สแกนหน้าจะใช้ไม่ได้"
fi

OFFLINE=$(grep -E '^KIOSK_STT_OFFLINE_ONLY=' server/.env 2>/dev/null | tail -1 | cut -d= -f2 | tr -d '[:space:]')
if [ "$OFFLINE" = "1" ]; then
  ok "ห้ามดาวน์โหลดโมเดลระหว่างให้บริการ"
else
  warn "ยังไม่ได้ตั้ง KIOSK_STT_OFFLINE_ONLY=1 — ตู้อาจพยายามโหลดโมเดลกลางคัน"
fi

# ------------------------------------------------------------
echo
echo "3. เครื่อง"

MEM=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}')
if [ -n "$MEM" ]; then
  if [ "$MEM" -ge 7000 ]; then ok "หน่วยความจำ ${MEM} MB"
  elif [ "$MEM" -ge 3500 ]; then warn "หน่วยความจำ ${MEM} MB — ควรใช้โมเดลถอดเสียงรุ่น base"
  else bad "หน่วยความจำ ${MEM} MB น้อยเกินไปสำหรับโมเดลรู้จำใบหน้า"
  fi
fi

if [ -e /dev/video0 ] || (command -v libcamera-hello >/dev/null 2>&1 && libcamera-hello --list-cameras >/dev/null 2>&1); then
  ok "ตรวจพบกล้อง"
else
  warn "ไม่พบกล้อง — ตู้จะใช้ได้เฉพาะการกรอกรหัสนักศึกษา"
fi

TZ_NOW=$(timedatectl show -p Timezone --value 2>/dev/null || echo '?')
if [ "$TZ_NOW" = "Asia/Bangkok" ]; then
  ok "เขตเวลา $TZ_NOW"
else
  warn "เขตเวลาเครื่องคือ $TZ_NOW — ตู้บังคับใช้เวลาไทยอยู่แล้ว แต่บันทึกจะอ่านยาก"
fi

# ------------------------------------------------------------
echo
echo "4. บริการที่กำลังทำงาน"

if curl -sf --max-time 5 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
  ok "เซิร์ฟเวอร์ตอบที่พอร์ต 8000"
  FACE=$(curl -sf --max-time 5 http://127.0.0.1:8000/api/face/status 2>/dev/null)
  echo "$FACE" | grep -q '"running":true' && ok "ลูปกล้องทำงานอยู่" \
    || warn "ลูปกล้องไม่ทำงาน — ดูสาเหตุที่ /api/face/status"
  curl -sf --max-time 5 http://127.0.0.1:8000/api/voice/status 2>/dev/null | grep -q '"ready":true' \
    && ok "ระบบถอดเสียงพร้อม" || warn "ระบบถอดเสียงยังไม่พร้อม"
else
  warn "เซิร์ฟเวอร์ยังไม่ทำงาน (ข้ามการตรวจส่วนนี้)"
fi

# ------------------------------------------------------------
echo
echo "============================================================"
echo "ผ่าน $PASS · เตือน $WARN · ต้องแก้ $FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo
  echo "ยังเปิดให้บริการไม่ได้ ต้องแก้ข้อที่ขึ้นว่า [ตก] ก่อน"
  exit 1
fi
[ "$WARN" -gt 0 ] && echo "เปิดบริการได้ แต่บางฟีเจอร์จะใช้ไม่ได้ตามที่เตือนไว้"
exit 0
