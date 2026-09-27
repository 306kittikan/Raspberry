#!/usr/bin/env bash
# ตั้งค่าจอของตู้ เรียกตอนเข้าเซสชันกราฟิก
#
# ติดตั้งผ่าน ~/.config/autostart/kiosk-display.desktop
# ดูขั้นตอนเต็มใน docs/deploy-raspberry-pi.md ข้อ 8.3

# ปิดการดับจอทุกรูปแบบ ตู้ต้องสว่างตลอดเวลาทำการ
# คนเดินผ่านต้องเห็นว่าตู้ใช้งานได้ ไม่ใช่จอดำที่ดูเหมือนเครื่องเสีย
xset s off        2>/dev/null
xset -dpms        2>/dev/null
xset s noblank    2>/dev/null

# ซ่อนเคอร์เซอร์เมาส์หลังไม่ขยับครึ่งวินาที
# จอสัมผัสไม่ควรมีลูกศรค้างอยู่กลางจอ
command -v unclutter >/dev/null && unclutter -idle 0.5 -root &

# หมุนจอเป็นแนวตั้ง เฉพาะเมื่อใช้ X11
# ถ้าใช้ Wayland ให้ตั้งใน ~/.config/wayfire.ini แทน (ดูคู่มือข้อ 8.4)
if [ "${XDG_SESSION_TYPE:-}" = "x11" ]; then
  OUTPUT=$(xrandr --query | awk '/ connected/{print $1; exit}')
  [ -n "$OUTPUT" ] && xrandr --output "$OUTPUT" --rotate left
fi
