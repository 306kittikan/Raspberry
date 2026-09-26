// ============================================================
// จัดรูปแบบเวลาสำหรับแสดงผลเท่านั้น
//
// การคำนวณคาบเรียนถัดไป ตารางวันนี้ และตารางทั้งสัปดาห์
// ย้ายไปอยู่ที่เซิร์ฟเวอร์ (server/app/repo.py) แล้ว
// เพื่อให้คำตอบเหมือนกันไม่ว่าจะเข้าทางหน้าจอหรือผ่านผู้ช่วยตอบคำถาม
// เหลือไว้ที่นี่เฉพาะสิ่งที่ต้องเดินตามนาฬิกาของหน้าจอทุกวินาที
// ============================================================

const thaiFullDate = new Intl.DateTimeFormat('th-TH-u-ca-buddhist', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})

export function formatThaiDate(d) {
  return thaiFullDate.format(d)
}

/** "14:05" */
export function formatClock(d) {
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/** ข้อความนับถอยหลัง เช่น "อีก 1 ชั่วโมง 20 นาที" */
export function formatCountdown(ms) {
  if (ms <= 0) return 'ถึงเวลาเรียนแล้ว'
  const totalMinutes = Math.floor(ms / 60000)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60

  if (totalMinutes < 1) {
    const seconds = Math.max(1, Math.floor(ms / 1000))
    return `อีก ${seconds} วินาที`
  }
  if (hours >= 24) {
    const days = Math.floor(hours / 24)
    const restHours = hours % 24
    return restHours === 0 ? `อีก ${days} วัน` : `อีก ${days} วัน ${restHours} ชั่วโมง`
  }
  if (hours === 0) return `อีก ${minutes} นาที`
  if (minutes === 0) return `อีก ${hours} ชั่วโมง`
  return `อีก ${hours} ชั่วโมง ${minutes} นาที`
}
