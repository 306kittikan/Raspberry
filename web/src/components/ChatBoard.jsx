import React, { useEffect, useRef } from 'react'
import { useKiosk } from '../state/KioskProvider'
import SourceBadge from './SourceBadge'
import { IconKeypad, IconMic, IconSparkle } from './Icons'

/**
 * กระดานสนทนา — คำถามและคำตอบเรียงต่อกันเหมือนแชท
 *
 * เก็บอยู่บนหน้าจอเท่านั้น ไม่ส่งขึ้นเซิร์ฟเวอร์และไม่บันทึกลงฐานข้อมูล
 * เมื่อออกจากระบบหรือหมดเวลาใช้งาน ทั้งกระดานจะถูกล้างทิ้งพร้อมข้อมูลอื่น
 *
 * ทุกคำตอบยังติดป้ายบอกแหล่งที่มาเหมือนเดิม ไม่มีข้อยกเว้น
 */

function Meta({ turn }) {
  const Icon = turn.channel === 'เสียง' ? IconMic : IconKeypad
  return (
    <span className="flex items-center gap-2 text-[19px] text-ink-mute">
      <Icon className="h-6 w-6" />
      {turn.at.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', hour12: false })}
    </span>
  )
}

export default function ChatBoard({ className = '' }) {
  const { messages, answerPending, micState } = useKiosk()
  const endRef = useRef(null)

  // เลื่อนไปข้อความล่าสุดเสมอ ผู้ใช้ยืนอยู่หน้าตู้ จะไม่ย้อนอ่านเอง
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, answerPending, micState])

  if (messages.length === 0 && !answerPending) return null

  return (
    <div className={`space-y-6 ${className}`}>
      {messages.map((turn) => (
        <div key={turn.id} className="space-y-3 animate-rise-in">
          {/* ---- ฝั่งนักศึกษา ---- */}
          <div className="flex justify-end">
            <div className="max-w-[86%] rounded-[24px] rounded-br-[10px] bg-brand-700 px-8 py-6 text-white">
              <div className="flex items-center justify-end gap-3 opacity-70">
                <Meta turn={turn} />
              </div>
              <p className="mt-2 text-body-lg font-semibold leading-snug">{turn.asked}</p>
            </div>
          </div>

          {/* ---- ฝั่งตู้ ---- */}
          <div className="flex justify-start">
            <div
              className={`max-w-[92%] rounded-[24px] rounded-bl-[10px] border-2 px-8 py-6 ${
                turn.answer?.source === 'ai'
                  ? 'border-ai-200 bg-ai-50'
                  : turn.answer?.source === 'none'
                    ? 'border-alert-100 bg-alert-50'
                    : 'border-brand-200 bg-white'
              }`}
            >
              <SourceBadge source={turn.answer?.source} reference={turn.answer?.ref} />

              <p className="mt-4 text-h3 font-bold leading-tight text-brand-900">
                {turn.answer?.title}
              </p>

              {turn.answer?.lines?.length ? (
                <ul className="mt-3 space-y-2">
                  {turn.answer.lines.map((line, i) => (
                    <li
                      key={`${turn.id}-${i}`}
                      className="flex gap-3 text-body leading-snug text-ink-soft"
                    >
                      <span className="mt-[14px] h-[7px] w-[7px] shrink-0 rounded-full bg-brand-400" />
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          </div>
        </div>
      ))}

      {/* ---- กำลังคิดคำตอบ ---- */}
      {answerPending || micState === 'processing' ? (
        <div className="flex justify-start">
          <div className="flex items-center gap-4 rounded-[24px] rounded-bl-[10px] border-2 border-brand-200 bg-white px-8 py-6">
            <IconSparkle className="h-8 w-8 text-brand-600" />
            <span className="flex gap-2">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="h-3 w-3 rounded-full bg-brand-500 animate-dot"
                  style={{ animationDelay: `${i * 180}ms` }}
                />
              ))}
            </span>
            <p className="text-body font-semibold text-ink-soft">กำลังหาคำตอบ…</p>
          </div>
        </div>
      ) : null}

      <div ref={endRef} />
    </div>
  )
}
