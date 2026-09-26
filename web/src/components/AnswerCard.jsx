import React from 'react'
import SourceBadge from './SourceBadge'
import { Button } from './ui'
import { IconArrowRight, IconFace } from './Icons'
import { useKiosk } from '../state/KioskProvider'

/** พื้นที่แสดงคำตอบ — ทุกคำตอบต้องมีป้ายบอกที่มาเสมอ */
export default function AnswerCard({ answer, pending }) {
  const { startScan } = useKiosk()

  if (pending) {
    return (
      <div className="card flex items-center gap-6 p-10">
        <span className="h-14 w-14 rounded-full border-[6px] border-brand-100 border-t-brand-600 animate-spin-slow" />
        <p className="text-body-lg font-semibold text-ink-soft">กำลังค้นหาคำตอบ…</p>
      </div>
    )
  }

  if (!answer) return null

  const tone =
    answer.source === 'ai'
      ? 'border-ai-100 bg-ai-50'
      : answer.source === 'db'
        ? 'border-brand-200 bg-white'
        : 'border-alert-100 bg-alert-50'

  return (
    <div className={`rounded-[28px] border-2 p-10 animate-rise-in ${tone}`}>
      {answer.unclear ? null : <SourceBadge source={answer.source} reference={answer.ref} />}

      <h3 className="mt-6 text-h3 font-bold text-brand-900">{answer.title}</h3>

      <ul className="mt-5 space-y-3">
        {answer.lines.map((line) => (
          <li key={line} className="flex gap-4 text-body leading-relaxed text-ink">
            <span className="mt-[14px] h-[10px] w-[10px] shrink-0 rounded-full bg-brand-400" />
            <span>{line}</span>
          </li>
        ))}
      </ul>

      {answer.needAuth ? (
        <Button className="mt-8 w-full" size="lg" icon={IconFace} onClick={startScan}>
          ยืนยันตัวตนด้วยใบหน้า
          <IconArrowRight className="h-9 w-9" />
        </Button>
      ) : null}
    </div>
  )
}
