// ============================================================
// ตัวแปลคำถาม → คำตอบ พร้อมระบุ "แหล่งที่มา" เสมอ
//   db   = ข้อมูลจากระบบของสาขา (ตารางเรียน ห้อง กำหนดสอบ)
//   ai   = ตอบโดยผู้ช่วย AI ต้องมีชื่อเอกสารอ้างอิงเสมอ
//   none = ไม่พบข้อมูลในระบบ ห้ามเดาคำตอบ
// ============================================================

import { QUICK_QUESTIONS, DEPARTMENT, CONTACT_FALLBACK } from '../data/mockData'
import { findNextClass } from './time'

export function getQuestion(id) {
  return QUICK_QUESTIONS.find((q) => q.id === id) || null
}

/**
 * @param {string} questionId
 * @param {object} ctx { student, online, hasSchedule }
 * @returns answer object | null
 */
export function resolveAnswer(questionId, ctx) {
  const q = getQuestion(questionId)
  if (!q) return null

  const base = { questionId, kind: q.kind, label: q.label }
  const { student, hasSchedule } = ctx

  // ---- คำถามที่ต้องยืนยันตัวตนก่อน ----
  if (q.personal && !student) {
    return {
      ...base,
      source: 'none',
      title: 'ต้องยืนยันตัวตนก่อน',
      lines: [
        'คำถามนี้ต้องใช้ตารางเรียนส่วนบุคคล',
        'กรุณายืนยันตัวตนด้วยใบหน้า หรือกรอกรหัสนักศึกษาที่หน้าจอพัก',
      ],
      needAuth: true,
    }
  }

  // ---- ผู้ช่วย AI ต้องใช้อินเทอร์เน็ต ----
  if (q.source === 'ai' && !ctx.online) {
    return {
      ...base,
      source: 'none',
      title: 'ผู้ช่วย AI ไม่พร้อมใช้งานขณะออฟไลน์',
      lines: [
        'ขณะนี้ตู้ไม่ได้เชื่อมต่ออินเทอร์เน็ต จึงตอบคำถามที่ต้องใช้ผู้ช่วย AI ไม่ได้',
        'ตารางเรียนและกำหนดสอบยังใช้งานได้ตามปกติ',
      ],
      offlineBlocked: true,
    }
  }

  switch (q.id) {
    case 'next-class': {
      if (!hasSchedule) return noScheduleAnswer(base)
      const next = findNextClass(student.schedule, new Date())
      if (!next) return noScheduleAnswer(base)
      return {
        ...base,
        source: 'db',
        title: next.ongoing ? 'คาบที่กำลังเรียนอยู่' : 'คาบเรียนถัดไปของคุณ',
        lines: [
          `${next.item.code} ${next.item.name}`,
          `เวลา ${next.item.start}–${next.item.end} น.`,
          `ห้อง ${next.item.room} · ${next.item.building} ชั้น ${next.item.floor}`,
        ],
      }
    }

    case 'room-floor': {
      if (!hasSchedule) return noScheduleAnswer(base)
      const next = findNextClass(student.schedule, new Date())
      if (!next) return noScheduleAnswer(base)
      return {
        ...base,
        source: 'db',
        title: `ห้อง ${next.item.room}`,
        lines: [
          `อยู่ชั้น ${next.item.floor} ${next.item.building}`,
          `ใช้เรียนวิชา ${next.item.name} เวลา ${next.item.start}–${next.item.end} น.`,
          'ขึ้นลิฟต์ฝั่งซ้ายของโถงทางเข้า แล้วเลี้ยวขวา',
        ],
      }
    }

    case 'exam-subject': {
      if (!hasSchedule || !student.exams || student.exams.length === 0) {
        return {
          ...base,
          source: 'db',
          title: 'ยังไม่มีกำหนดสอบ',
          lines: ['ยังไม่มีประกาศกำหนดสอบในภาคการศึกษานี้', 'ติดตามประกาศจากสำนักงานสาขาวิชาฯ อีกครั้ง'],
        }
      }
      const exam = student.exams[0]
      return {
        ...base,
        source: 'db',
        title: `${exam.type}วิชา ${exam.name}`,
        lines: [
          `${exam.dateLabel} เวลา ${exam.time} น.`,
          `ห้องสอบ ${exam.room}`,
          `ดูกำหนดสอบทั้งหมดได้ที่แท็บ "กำหนดสอบ" บนหน้าหลัก`,
        ],
      }
    }

    case 'contact-teacher':
      return {
        ...base,
        source: 'db',
        title: 'ติดต่ออาจารย์ประจำสาขาวิชาฯ',
        lines: [
          `ห้องพักอาจารย์ ${DEPARTMENT.officeLocation}`,
          `เวลาราชการ ${DEPARTMENT.officeHours}`,
          `นัดหมายล่วงหน้าได้ที่ ${DEPARTMENT.officePhone} หรือ ${DEPARTMENT.officeEmail}`,
        ],
      }

    case 'office-hours':
      return {
        ...base,
        source: 'db',
        title: 'สำนักงานสาขาวิชาวิทยาการคอมพิวเตอร์',
        lines: [DEPARTMENT.officeLocation, `เปิดทำการ ${DEPARTMENT.officeHours}`, `โทร ${DEPARTMENT.officePhone}`],
      }

    // ---- กรณีไม่พบเอกสารอ้างอิง: ห้ามเดาคำตอบ ----
    case 'scholarship-detail':
      return {
        ...base,
        source: 'none',
        title: 'ไม่พบข้อมูลนี้ในระบบ',
        lines: ['ระบบไม่พบเอกสารอ้างอิงสำหรับคำถามนี้ จึงไม่สามารถตอบได้', ...CONTACT_FALLBACK],
      }

    default:
      // ---- คำตอบจากผู้ช่วย AI พร้อมเอกสารอ้างอิง ----
      if (q.source === 'ai') {
        return {
          ...base,
          source: 'ai',
          ref: q.ref,
          title: q.label,
          lines: q.answer || [],
        }
      }
      return {
        ...base,
        source: 'none',
        title: 'ไม่พบข้อมูลนี้ในระบบ',
        lines: ['ระบบไม่พบข้อมูลสำหรับคำถามนี้', ...CONTACT_FALLBACK],
      }
  }
}

function noScheduleAnswer(base) {
  return {
    ...base,
    source: 'db',
    title: 'ยังไม่มีข้อมูลตารางเรียน',
    lines: ['ยังไม่มีข้อมูลตารางเรียนภาคการศึกษานี้ กรุณาติดต่อสำนักงานสาขา', ...CONTACT_FALLBACK],
  }
}

/** คำตอบเมื่อฟังเสียงไม่ชัด */
export const UNCLEAR_ANSWER = {
  source: 'none',
  unclear: true,
  title: 'ขออภัย ไม่ได้ยินชัดเจน',
  lines: ['ลองพูดอีกครั้งหรือแตะเลือกคำถามด้านล่าง'],
}
