import React from 'react'
import { useKiosk } from '../state/KioskProvider'
import { IconMic } from './Icons'

const BARS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

/**
 * ปุ่มไมโครโฟนขนาดใหญ่ + สถานะ 3 แบบที่ต่างกันชัดเจน
 *   พร้อมฟัง / กำลังฟัง (แถบคลื่นเสียงเคลื่อนไหว) / กำลังประมวลผล
 * เมื่อออฟไลน์จะเป็นสีเทาพร้อมคำอธิบาย เพราะสั่งงานด้วยเสียงต้องใช้ผู้ช่วย AI
 */
export default function MicPanel() {
  const { micState, transcript, online, startListening } = useKiosk()
  const disabled = !online

  const label = disabled
    ? 'สั่งงานด้วยเสียงไม่พร้อมใช้งาน'
    : micState === 'listening'
      ? 'กำลังฟัง…'
      : micState === 'processing'
        ? 'กำลังประมวลผล…'
        : 'พร้อมฟัง — แตะเพื่อพูด'

  const ring = disabled
    ? 'border-brand-100 bg-white'
    : micState === 'listening'
      ? 'border-brand-600 bg-brand-50'
      : micState === 'processing'
        ? 'border-ai-600 bg-ai-50'
        : 'border-brand-200 bg-white'

  return (
    <div className={`rounded-[32px] border-2 p-10 ${ring}`}>
      <div className="flex items-center gap-10">
        <div className="relative flex h-[184px] w-[184px] shrink-0 items-center justify-center">
          {micState === 'listening' && !disabled ? (
            <span className="absolute inset-0 rounded-full border-4 border-brand-400 animate-pulse-ring" />
          ) : null}

          <button
            type="button"
            onClick={startListening}
            disabled={disabled || micState !== 'idle'}
            aria-label="พูดคำถาม"
            className={`press relative flex h-[184px] w-[184px] items-center justify-center rounded-full border-4 ${
              disabled
                ? 'border-brand-100 bg-brand-50 text-ink-mute'
                : micState === 'listening'
                  ? 'border-brand-700 bg-brand-700 text-white'
                  : micState === 'processing'
                    ? 'border-ai-600 bg-ai-600 text-white'
                    : 'border-brand-700 bg-white text-brand-700 active:bg-brand-100'
            }`}
          >
            {micState === 'processing' && !disabled ? (
              <span className="h-20 w-20 rounded-full border-[8px] border-white/30 border-t-white animate-spin-slow" />
            ) : (
              <IconMic className="h-24 w-24" strokeWidth={2.2} />
            )}
          </button>
        </div>

        <div className="min-w-0 flex-1">
          <p
            className={`text-h3 font-bold ${
              disabled
                ? 'text-ink-mute'
                : micState === 'processing'
                  ? 'text-ai-700'
                  : 'text-brand-800'
            }`}
          >
            {label}
          </p>

          {disabled ? (
            <p className="mt-3 text-body text-ink-soft">
              ต้องเชื่อมต่ออินเทอร์เน็ตจึงจะสั่งงานด้วยเสียงได้ ระหว่างนี้แตะเลือกคำถามด้านล่างได้ตามปกติ
            </p>
          ) : micState === 'listening' ? (
            <div className="mt-6 flex h-[72px] items-center gap-[10px]">
              {BARS.map((i) => (
                <span
                  key={i}
                  className="wave-bar w-[14px] rounded-full bg-brand-600"
                  style={{ height: '72px', animationDelay: `${i * 70}ms` }}
                />
              ))}
            </div>
          ) : micState === 'processing' ? (
            <p className="mt-3 text-body text-ink-soft">กำลังค้นหาคำตอบจากระบบของสาขา…</p>
          ) : (
            <p className="mt-3 text-body text-ink-soft">
              พูดคำถามได้เลย เช่น “คาบต่อไปเรียนที่ห้องไหน” หรือแตะเลือกคำถามด้านล่าง
            </p>
          )}
        </div>
      </div>

      {/* แสดงข้อความที่ระบบได้ยิน เพื่อให้ผู้ใช้ตรวจสอบก่อนรับคำตอบ */}
      {transcript ? (
        <div className="mt-8 rounded-[24px] border-2 border-brand-200 bg-white px-8 py-6 animate-rise-in">
          <p className="text-label font-semibold text-ink-mute">ระบบได้ยินว่า</p>
          <p className="mt-2 text-h3 font-bold text-brand-900">“{transcript}”</p>
        </div>
      ) : null}
    </div>
  )
}
