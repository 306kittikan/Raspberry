// ============================================================
// ฟังก์ชันจัดรูปแบบเวลา/วันที่ และคำนวณคาบเรียนถัดไป
// ============================================================

const thaiFullDate = new Intl.DateTimeFormat('th-TH-u-ca-buddhist', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})

const thaiShortDate = new Intl.DateTimeFormat('th-TH-u-ca-buddhist', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})

export function formatThaiDate(d) {
  return thaiFullDate.format(d)
}

export function formatThaiShortDate(d) {
  return thaiShortDate.format(d)
}

/** "14:05" */
export function formatClock(d) {
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/** "14:05:32" */
export function formatClockSeconds(d) {
  return `${formatClock(d)}:${String(d.getSeconds()).padStart(2, '0')}`
}

/** แปลง "09:30" + วันที่ฐาน → Date */
function atTime(baseDate, hhmm) {
  const [h, m] = hhmm.split(':').map(Number)
  const d = new Date(baseDate)
  d.setHours(h, m, 0, 0)
  return d
}

function byStart(a, b) {
  return a.start.localeCompare(b.start)
}

/** คาบเรียนของ "วันนี้" ตามวันในสัปดาห์ปัจจุบัน */
export function classesToday(schedule, now) {
  return schedule.filter((s) => s.day === now.getDay()).sort(byStart)
}

/** จัดกลุ่มตารางทั้งสัปดาห์ จันทร์–ศุกร์ */
export function classesByWeek(schedule) {
  const week = {}
  for (let day = 1; day <= 5; day += 1) {
    week[day] = schedule.filter((s) => s.day === day).sort(byStart)
  }
  return week
}

/**
 * หาคาบเรียนถัดไป (มองไปข้างหน้าได้สูงสุด 8 วัน)
 * ถ้ากำลังเรียนอยู่ จะคืนคาบปัจจุบันพร้อม ongoing = true
 * ถ้าวันนี้ไม่มีเรียนแล้ว จะข้ามไปคาบแรกของวันเรียนถัดไปโดยอัตโนมัติ
 */
export function findNextClass(schedule, now) {
  if (!schedule || schedule.length === 0) return null

  for (let offset = 0; offset < 8; offset += 1) {
    const day = new Date(now)
    day.setDate(day.getDate() + offset)
    const items = schedule.filter((s) => s.day === day.getDay()).sort(byStart)

    for (const item of items) {
      const start = atTime(day, item.start)
      const end = atTime(day, item.end)
      if (now < end) {
        return {
          item,
          start,
          end,
          dayOffset: offset,
          ongoing: now >= start,
          isToday: offset === 0,
        }
      }
    }
  }
  return null
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

/** คำเรียกวันแบบสัมพัทธ์: วันนี้ / พรุ่งนี้ / วันจันทร์ */
export function relativeDayLabel(dayOffset, date) {
  if (dayOffset === 0) return 'วันนี้'
  if (dayOffset === 1) return 'พรุ่งนี้'
  return new Intl.DateTimeFormat('th-TH', { weekday: 'long' }).format(date)
}
