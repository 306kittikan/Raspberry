import React, { useEffect, useRef, useState } from 'react'
import { useKiosk } from '../state/KioskProvider'
import SourceBadge from './SourceBadge'
import CameraView from './CameraView'
import {
  IconClose,
  IconDatabase,
  IconFace,
  IconIncognito,
  IconKeypad,
  IconMic,
  IconSend,
  IconSparkle,
} from './Icons'

/**
 * หน้าต่างแชทของผู้ช่วยตอบคำถาม
 *
 * รูปแบบเดียวกับแอปแชททั่วไป เพราะนักศึกษาคุ้นอยู่แล้ว ไม่ต้องเรียนรู้ใหม่
 *   แถบหัว     รูปผู้ใช้ + ชื่อ + ปุ่มปิด
 *   เนื้อหา    ฟองข้อความสองฝั่ง ฝั่งขวาคือนักศึกษา ฝั่งซ้ายคือตู้
 *   ช่องพิมพ์  พิมพ์เอง · ปุ่มไมโครโฟน · ปุ่มคำถามยอดนิยม · ปุ่มส่ง
 *
 * ถามได้สามทาง (แตะ · พิมพ์ · พูด) ทุกทางผ่านกติกาเดียวกัน
 * คำถามเรื่องตารางเรียน ห้องเรียน กำหนดสอบ ไปที่ฐานข้อมูลเสมอ ไม่ผ่าน AI
 *
 * บทสนทนาเก็บบนหน้าจอเท่านั้น ล้างทิ้งเมื่อออกจากระบบ
 */

/** ความยาวสูงสุดของคำถามที่พิมพ์ ตรงกับที่เซิร์ฟเวอร์รับ */
const MAX_LEN = 300

function Bubble({ side, children, tone = '' }) {
  const mine = side === 'student'
  return (
    <div className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`relative max-w-[86%] px-8 py-6 ${
          mine
            ? 'rounded-[26px] rounded-br-[8px] bg-brand-700 text-white'
            : `rounded-[26px] rounded-bl-[8px] border-2 bg-white ${tone}`
        }`}
      >
        {children}
      </div>
    </div>
  )
}

function Answer({ answer }) {
  return (
    <>
      <SourceBadge source={answer?.source} reference={answer?.ref} />
      <p className="mt-4 text-h3 font-bold leading-tight text-brand-900">{answer?.title}</p>
      {answer?.lines?.length ? (
        <ul className="mt-3 space-y-2">
          {answer.lines.map((line, i) => (
            <li key={i} className="flex gap-3 text-body leading-snug text-ink-soft">
              <span className="mt-[14px] h-[7px] w-[7px] shrink-0 rounded-full bg-brand-400" />
              <span>{line}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </>
  )
}

export default function ChatWindow() {
  const {
    messages,
    answerPending,
    micState,
    transcript,
    student,
    anonymous,
    online,
    sttReady,
    voiceSupported,
    cameraOk,
    quickQuestions,
    askQuestion,
    askText,
    startListening,
    endSession,
    markActivity,
  } = useKiosk()

  const [draft, setDraft] = useState('')
  const [showQuick, setShowQuick] = useState(false)
  const endRef = useRef(null)
  const inputRef = useRef(null)

  const busy = answerPending || micState === 'processing'
  const listening = micState === 'listening'
  const micDisabled = !sttReady || !voiceSupported

  // เลื่อนไปข้อความล่าสุดเสมอ ผู้ใช้ยืนอยู่หน้าตู้ จะไม่ย้อนอ่านเอง
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, answerPending, micState, transcript, showQuick])

  const send = () => {
    const text = draft.trim()
    if (!text || busy) return
    setDraft('')
    setShowQuick(false)
    askText(text)
    inputRef.current?.focus()
  }

  const pickQuick = (id) => {
    setShowQuick(false)
    askQuestion(id)
  }

  return (
    <div className="flex h-full w-full flex-col overflow-hidden rounded-[32px] border-2 border-brand-100 bg-white shadow-[0_18px_50px_rgba(11,97,54,0.18)]">
      {/* ---- แถบหัว ---- */}
      <header className="flex shrink-0 items-center gap-5 bg-brand-700 px-8 py-6 text-white">
        <span className="flex h-[84px] w-[84px] shrink-0 items-center justify-center overflow-hidden rounded-full bg-white/15">
          {cameraOk && !anonymous ? (
            <CameraView className="h-full w-full" rounded="rounded-full" />
          ) : anonymous ? (
            <IconIncognito className="h-11 w-11 text-white" />
          ) : (
            <IconFace className="h-11 w-11 text-white" />
          )}
        </span>

        <div className="min-w-0 flex-1">
          <p className="truncate text-h3 font-bold leading-tight">ผู้ช่วยตอบคำถาม</p>
          <p className="truncate text-label leading-tight text-brand-100">
            {anonymous && !student
              ? 'โหมดไม่ระบุตัวตน — ไม่แสดงข้อมูลส่วนบุคคล'
              : student
                ? `คุยกับ ${student.name}`
                : 'ทุกคำตอบบอกที่มาของข้อมูลเสมอ'}
          </p>
        </div>

        <button
          type="button"
          onClick={() => endSession('manual')}
          aria-label="ปิดหน้าต่างแชท"
          className="press tap flex h-[80px] w-[80px] shrink-0 items-center justify-center rounded-full active:bg-white/15"
        >
          <IconClose className="h-11 w-11" strokeWidth={2.4} />
        </button>
      </header>

      {/* ---- บทสนทนา ---- */}
      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto bg-brand-50/60 px-8 py-8">
        {messages.length === 0 ? (
          <Bubble side="kiosk" tone="border-brand-200">
            <p className="text-h3 font-bold leading-tight text-brand-900">
              สวัสดีครับ ถามได้เลย
            </p>
            <p className="mt-3 text-body leading-snug text-ink-soft">
              พิมพ์คำถาม แตะปุ่มไมโครโฟนเพื่อพูด หรือเลือกจากคำถามยอดนิยมด้านล่าง
            </p>
          </Bubble>
        ) : null}

        {messages.map((turn) => (
          <div key={turn.id} className="space-y-4 animate-rise-in">
            <Bubble side="student">
              <span className="flex items-center justify-end gap-2 text-[19px] opacity-70">
                {turn.channel === 'เสียง' ? (
                  <IconMic className="h-6 w-6" />
                ) : (
                  <IconKeypad className="h-6 w-6" />
                )}
                {turn.at.toLocaleTimeString('th-TH', {
                  hour: '2-digit',
                  minute: '2-digit',
                  hour12: false,
                })}
              </span>
              <p className="mt-2 text-body-lg font-semibold leading-snug">{turn.asked}</p>
            </Bubble>

            <Bubble
              side="kiosk"
              tone={
                turn.answer?.source?.startsWith('ai')
                  ? 'border-ai-200'
                  : turn.answer?.source === 'none'
                    ? 'border-alert-100'
                    : 'border-brand-200'
              }
            >
              <Answer answer={turn.answer} />
            </Bubble>
          </div>
        ))}

        {/* สิ่งที่ระบบได้ยิน แสดงก่อนตอบ เพื่อให้ผู้ใช้ตรวจสอบได้ */}
        {transcript && busy ? (
          <Bubble side="student">
            <p className="text-body-lg font-semibold leading-snug opacity-80">“{transcript}”</p>
          </Bubble>
        ) : null}

        {busy ? (
          <Bubble side="kiosk" tone="border-brand-200">
            <div className="flex items-center gap-4">
              <IconSparkle className="h-8 w-8 shrink-0 text-brand-600" />
              <span className="flex gap-2">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="h-3 w-3 rounded-full bg-brand-500 animate-dot"
                    style={{ animationDelay: `${i * 180}ms` }}
                  />
                ))}
              </span>
              <p className="text-body font-semibold text-ink-soft">
                {micState === 'processing' ? 'กำลังฟังให้จบ…' : 'กำลังหาคำตอบ…'}
              </p>
            </div>
          </Bubble>
        ) : null}

        <div ref={endRef} />
      </div>

      {/* ---- คำถามยอดนิยม (เปิด/ปิดได้) ---- */}
      {showQuick ? (
        <div className="max-h-[520px] shrink-0 overflow-y-auto border-t-2 border-brand-100 bg-white px-8 py-6 animate-rise-in">
          <div className="mb-4 flex items-center gap-4">
            <h2 className="text-h3 font-bold text-brand-900">คำถามยอดนิยม</h2>
            <span className="flex items-center gap-2 text-[21px] text-ink-mute">
              <IconDatabase className="h-6 w-6 text-brand-600" /> ฐานข้อมูล
              <IconSparkle className="ml-3 h-6 w-6 text-ai-600" /> AI
            </span>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {quickQuestions.map((q) => {
              const aiBlocked = q.source === 'ai' && !online
              const needAuth = q.personal && !student
              return (
                <button
                  key={q.id}
                  type="button"
                  disabled={aiBlocked}
                  onClick={() => pickQuick(q.id)}
                  className={`press tap min-h-[104px] rounded-[22px] border-2 px-6 py-5 text-left text-body font-semibold leading-snug ${
                    aiBlocked
                      ? 'border-brand-100 bg-brand-50 text-ink-mute'
                      : q.source === 'ai'
                        ? 'border-ai-200 bg-ai-50 text-ai-700 active:bg-ai-100'
                        : 'border-brand-200 bg-white text-brand-800 active:bg-brand-100'
                  }`}
                >
                  <span className="flex items-start gap-3">
                    {q.source === 'ai' ? (
                      <IconSparkle className="mt-1 h-6 w-6 shrink-0" />
                    ) : (
                      <IconDatabase className="mt-1 h-6 w-6 shrink-0" />
                    )}
                    <span>
                      {q.label}
                      {needAuth ? (
                        <span className="block text-[20px] font-normal text-ink-mute">
                          ต้องยืนยันตัวตนก่อน
                        </span>
                      ) : null}
                    </span>
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      ) : null}

      {/* ---- ช่องพิมพ์ ---- */}
      <div className="shrink-0 border-t-2 border-brand-100 bg-white px-8 py-6">
        <div
          className={`rounded-[26px] border-2 px-6 py-5 ${
            listening ? 'border-brand-600 bg-brand-50' : 'border-brand-300 bg-white'
          }`}
        >
          <input
            ref={inputRef}
            type="text"
            value={draft}
            maxLength={MAX_LEN}
            disabled={busy}
            onChange={(e) => {
              markActivity()
              setDraft(e.target.value)
            }}
            onKeyDown={(e) => e.key === 'Enter' && send()}
            placeholder={listening ? 'กำลังฟัง… พูดได้เลย' : 'ถามอะไรก็ได้…'}
            className="w-full bg-transparent text-body-lg text-brand-900 outline-none placeholder:text-ink-mute disabled:text-ink-mute"
          />

          <div className="mt-4 flex items-center gap-4">
            <button
              type="button"
              onClick={startListening}
              disabled={micDisabled || micState === 'processing'}
              aria-label={listening ? 'พูดจบแล้ว' : 'พูดคำถาม'}
              className={`press tap flex h-[76px] w-[76px] shrink-0 items-center justify-center rounded-full border-2 ${
                micDisabled
                  ? 'border-brand-100 bg-brand-50 text-ink-mute'
                  : listening
                    ? 'border-brand-700 bg-brand-700 text-white'
                    : 'border-brand-300 bg-white text-brand-700 active:bg-brand-100'
              }`}
            >
              <IconMic className="h-10 w-10" strokeWidth={2.2} />
            </button>

            <button
              type="button"
              onClick={() => {
                markActivity()
                setShowQuick((v) => !v)
              }}
              aria-label="คำถามยอดนิยม"
              className={`press tap flex h-[76px] w-[76px] shrink-0 items-center justify-center rounded-full border-2 ${
                showQuick
                  ? 'border-brand-700 bg-brand-100 text-brand-800'
                  : 'border-brand-300 bg-white text-brand-700 active:bg-brand-100'
              }`}
            >
              <IconDatabase className="h-9 w-9" />
            </button>

            {listening ? (
              <span className="flex items-end gap-[7px]">
                {[0, 1, 2, 3, 4, 5].map((i) => (
                  <span
                    key={i}
                    className="wave-bar w-[9px] rounded-full bg-brand-600"
                    style={{ height: '44px', animationDelay: `${i * 80}ms` }}
                  />
                ))}
              </span>
            ) : null}

            <button
              type="button"
              onClick={send}
              disabled={!draft.trim() || busy}
              aria-label="ส่งคำถาม"
              className="press tap ml-auto flex h-[76px] w-[76px] shrink-0 items-center justify-center rounded-full bg-brand-700 text-white active:bg-brand-800 disabled:bg-brand-100 disabled:text-ink-mute"
            >
              <IconSend className="h-10 w-10" />
            </button>
          </div>
        </div>

        {micDisabled ? (
          <p className="mt-3 text-[20px] text-ink-mute">
            ไมโครโฟนยังไม่พร้อม — พิมพ์คำถามหรือเลือกจากคำถามยอดนิยมได้ตามปกติ
          </p>
        ) : null}
      </div>
    </div>
  )
}
