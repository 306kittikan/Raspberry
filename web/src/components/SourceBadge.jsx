import React from 'react'
import { IconDatabase, IconSparkle, IconWarning } from './Icons'

/**
 * ป้ายบอกที่มาของคำตอบ — บังคับให้มีทุกคำตอบ
 *  db   : เขียว + ไอคอนฐานข้อมูล  → "ข้อมูลจากระบบของสาขา"
 *  ai   : ม่วง + ไอคอนประกาย      → "ตอบโดยผู้ช่วย AI · อ้างอิง: {ชื่อเอกสาร}"
 *  none : ส้ม  + ไอคอนเตือน       → ไม่พบข้อมูลในระบบ
 */
export default function SourceBadge({ source, reference, className = '' }) {
  if (source === 'db') {
    return (
      <span
        className={`inline-flex items-center gap-3 rounded-full border-2 border-brand-600 bg-brand-100 px-6 py-3 text-label font-semibold text-brand-800 ${className}`}
      >
        <IconDatabase className="h-8 w-8 shrink-0" />
        ข้อมูลจากระบบของสาขา
      </span>
    )
  }

  if (source === 'ai') {
    return (
      <span
        className={`inline-flex items-center gap-3 rounded-full border-2 border-ai-600 bg-ai-50 px-6 py-3 text-label font-semibold text-ai-700 ${className}`}
      >
        <IconSparkle className="h-8 w-8 shrink-0" />
        <span>
          ตอบโดยผู้ช่วย AI
          {reference ? <span className="font-normal"> · อ้างอิง: {reference}</span> : null}
        </span>
      </span>
    )
  }

  return (
    <span
      className={`inline-flex items-center gap-3 rounded-full border-2 border-alert-700 bg-alert-50 px-6 py-3 text-label font-semibold text-alert-700 ${className}`}
    >
      <IconWarning className="h-8 w-8 shrink-0" />
      ไม่พบข้อมูลในระบบของสาขา
    </span>
  )
}
