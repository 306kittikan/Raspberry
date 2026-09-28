import React from 'react'
import { useKiosk } from '../state/KioskProvider'
import CameraView from './CameraView'
import { formatClock, formatThaiDate } from '../lib/time'
import { IconLogo, IconMic, IconSparkle, IconUsers } from './Icons'

/**
 * แผงด้านข้างสำหรับจอคอมพิวเตอร์แนวนอน
 *
 * ทำหน้าที่เป็น "คู่สนทนา" ของนักศึกษา — เห็นหน้าตัวเองอยู่ตรงข้าม
 * พร้อมสิ่งที่ตู้ได้ยินและสิ่งที่ตู้ตอบ เหมือนคุยกันอยู่คนละฝั่งโต๊ะ
 *
 * บนตู้จริง (จอแนวตั้ง) แผงนี้ไม่ถูกแสดง เพราะไม่มีพื้นที่เหลือ
 * หน้าจอผู้ช่วยจึงมีภาพกล้องขนาดย่อในตัวแทน
 */

const MIC_STATES = {
  listening: { label: 'กำลังฟัง', tone: 'text-brand-200', ring: 'border-brand-400' },
  processing: { label: 'กำลังคิด', tone: 'text-ai-300', ring: 'border-ai-400' },
  idle: { label: 'พร้อมฟัง', tone: 'text-white/50', ring: 'border-white/15' },
}

function Bubble({ who, text, tone }) {
  return (
    <div className={`rounded-[22px] px-6 py-5 ${tone}`}>
      <p className="text-[19px] font-semibold opacity-70">{who}</p>
      <p className="mt-2 text-[24px] font-bold leading-snug">{text}</p>
    </div>
  )
}

export default function PresencePanel() {
  const {
    now,
    department,
    student,
    micState,
    transcript,
    answer,
    faceSim,
    screen,
    cameraOk,
  } = useKiosk()

  const mic = MIC_STATES[micState] ?? MIC_STATES.idle
  const scanning = screen === 'scan'
  const multi = scanning && faceSim === 'multi'

  // แสดงคำตอบล่าสุดเป็นบับเบิลฝั่งตู้ ให้รู้สึกเหมือนบทสนทนา
  const reply = answer ? [answer.title, ...(answer.lines ?? [])].filter(Boolean)[0] : null

  return (
    <div className="flex h-full w-full flex-col bg-[#04101B] px-10 py-9 text-white">
      {/* ---- หัวแผง ---- */}
      <div className="flex items-center gap-4">
        <IconLogo className="h-14 w-14 shrink-0 text-brand-500/70" />
        <div className="min-w-0">
          <p className="truncate text-[22px] font-bold leading-tight text-white/85">
            {department?.name ?? 'ตู้บริการข้อมูลอัจฉริยะ'}
          </p>
          <p className="truncate text-[18px] leading-tight text-white/40">
            {formatThaiDate(now)}
          </p>
        </div>
        <span className="ml-auto text-[34px] font-bold tabular-nums text-white/75">
          {formatClock(now)}
        </span>
      </div>

      {/* ---- ภาพผู้ใช้ ---- */}
      <div className="relative mt-8 flex-1 overflow-hidden">
        <CameraView className="h-full w-full" rounded="rounded-[32px]" />

        <div
          className={`pointer-events-none absolute inset-0 rounded-[32px] border-4 ${mic.ring} ${
            micState === 'listening' ? 'animate-pulse-ring' : ''
          }`}
        />

        {multi ? (
          <div className="absolute inset-x-6 top-6 flex items-center gap-3 rounded-[20px] bg-alert-50/95 px-6 py-4">
            <IconUsers className="h-8 w-8 shrink-0 text-alert-700" />
            <p className="text-[21px] font-bold text-alert-900">กรุณาใช้งานทีละคน</p>
          </div>
        ) : null}

        {/* ป้ายบอกว่าตอนนี้ตู้กำลังทำอะไรกับเสียง */}
        <div className="absolute inset-x-6 bottom-6 flex items-center gap-4 rounded-[20px] bg-black/55 px-6 py-4">
          <span
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-2 ${mic.ring}`}
          >
            {micState === 'processing' ? (
              <IconSparkle className="h-7 w-7 text-ai-300" />
            ) : (
              <IconMic className="h-7 w-7 text-white/80" />
            )}
          </span>
          <p className={`text-[22px] font-bold ${mic.tone}`}>{mic.label}</p>

          {micState === 'listening' ? (
            <span className="ml-auto flex items-end gap-[6px]">
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <span
                  key={i}
                  className="wave-bar w-[8px] rounded-full bg-brand-300"
                  style={{ height: '40px', animationDelay: `${i * 90}ms` }}
                />
              ))}
            </span>
          ) : null}
        </div>
      </div>

      {/* ---- บทสนทนา ---- */}
      <div className="mt-7 space-y-4">
        {transcript ? (
          <Bubble
            who={student ? student.name : 'คุณ'}
            text={`“${transcript}”`}
            tone="bg-white/10 text-white"
          />
        ) : null}

        {reply ? (
          <Bubble
            who="ตู้บริการข้อมูล"
            text={reply}
            tone={answer?.source === 'ai' ? 'bg-ai-600/25 text-ai-100' : 'bg-brand-600/25 text-brand-50'}
          />
        ) : null}

        {!transcript && !reply ? (
          <p className="rounded-[22px] border-2 border-dashed border-white/10 px-6 py-6 text-[21px] leading-snug text-white/35">
            {cameraOk
              ? 'ยืนหน้าตู้แล้วแตะปุ่มไมโครโฟนเพื่อเริ่มถามคำถาม'
              : 'กล้องใช้งานไม่ได้ ใช้การกรอกรหัสนักศึกษาแทนได้'}
          </p>
        ) : null}
      </div>
    </div>
  )
}
