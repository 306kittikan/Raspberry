// ============================================================
// บันทึกการใช้งาน (ไม่มีข้อมูลระบุตัวตนใด ๆ)
// รูปแบบ: { เวลา, ประเภทคำถาม, ช่องทาง, แหล่งคำตอบ }
// เตรียมไว้เชื่อมกับระบบเก็บสถิติภายหลัง
// ============================================================

export const CHANNEL = {
  VOICE: 'เสียง',
  TOUCH: 'แตะ',
}

export const SOURCE = {
  DB: 'ฐานข้อมูล',
  AI: 'AI',
}

const listeners = new Set()

export function subscribeToEvents(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

/**
 * @param {object} p
 * @param {string} p.kind    ประเภทคำถาม เช่น "ตารางเรียน"
 * @param {string} p.channel CHANNEL.VOICE | CHANNEL.TOUCH
 * @param {string} p.source  SOURCE.DB | SOURCE.AI
 */
export function logEvent({ kind, channel, source }) {
  const now = new Date()
  const entry = {
    เวลา: now.toISOString(),
    ประเภทคำถาม: kind,
    ช่องทาง: channel,
    แหล่งคำตอบ: source,
  }

  // eslint-disable-next-line no-console
  console.log('[kiosk-usage]', entry)

  const display = {
    id: `${now.getTime()}-${Math.random().toString(16).slice(2, 6)}`,
    time: `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`,
    kind,
    channel,
    source,
  }
  listeners.forEach((fn) => fn(display))
  return entry
}
