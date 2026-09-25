import React, { useEffect, useRef, useState } from 'react'
import { useKiosk, TIMING } from '../state/KioskProvider'
import { Button } from '../components/ui'
import OfflineBanner from '../components/OfflineBanner'
import TopBar from '../components/TopBar'
import { IconCameraOff, IconKeypad, IconUsers, IconWarning } from '../components/Icons'

/** กรอบนำตำแหน่งใบหน้า */
function FaceGuide({ tone }) {
  const color =
    tone === 'warn' ? 'border-alert-100' : tone === 'error' ? 'border-danger-100' : 'border-brand-200'
  return (
    <>
      <div className={`absolute left-1/2 top-1/2 h-[560px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-[210px] border-4 border-dashed ${color} opacity-70`} />
      {[
        'left-[calc(50%-230px)] top-[calc(50%-300px)] border-l-4 border-t-4 rounded-tl-[40px]',
        'left-[calc(50%+190px)] top-[calc(50%-300px)] border-r-4 border-t-4 rounded-tr-[40px]',
        'left-[calc(50%-230px)] top-[calc(50%+260px)] border-l-4 border-b-4 rounded-bl-[40px]',
        'left-[calc(50%+190px)] top-[calc(50%+260px)] border-r-4 border-b-4 rounded-br-[40px]',
      ].map((pos) => (
        <span
          key={pos}
          className={`absolute h-[40px] w-[40px] ${pos} ${
            tone === 'warn'
              ? 'border-alert-100'
              : tone === 'error'
                ? 'border-danger-100'
                : 'border-brand-300'
          }`}
        />
      ))}
    </>
  )
}

export default function FaceScanScreen() {
  const {
    cameraOk,
    faceSim,
    activeStudent,
    setCandidate,
    setUnknownReason,
    setScreen,
    endSession,
    goto,
    markActivity,
  } = useKiosk()

  const [elapsed, setElapsed] = useState(0)
  const timers = useRef([])

  useEffect(() => {
    const push = (fn, ms) => timers.current.push(setTimeout(fn, ms))

    // ---- กล้องใช้งานไม่ได้: แจ้งสถานะแล้วสลับไปกรอกรหัสนักศึกษาอัตโนมัติ ----
    if (!cameraOk) {
      push(() => {
        setUnknownReason('camera')
        setScreen('keypad')
      }, 3200)
    } else if (faceSim === 'recognized') {
      push(() => {
        setCandidate(activeStudent)
        setScreen('confirm')
      }, TIMING.FACE_DETECT_MS)
    } else if (faceSim === 'unknown') {
      push(() => {
        setUnknownReason('unrecognized')
        setScreen('unknown')
      }, TIMING.FACE_DETECT_MS)
    } else if (faceSim === 'notfound') {
      // หาใบหน้าไม่เจอเกิน 10 วินาที → เสนอทางเลือกอื่น
      push(() => {
        setUnknownReason('timeout')
        setScreen('unknown')
      }, TIMING.FACE_TIMEOUT_MS)
    }
    // faceSim === 'multi' : ค้างสถานะเตือนไว้ ไม่แสดงข้อมูลใด ๆ

    const tick = setInterval(() => setElapsed((e) => e + 1), 1000)
    return () => {
      timers.current.forEach(clearTimeout)
      timers.current = []
      clearInterval(tick)
    }
  }, [activeStudent, cameraOk, faceSim, setCandidate, setScreen, setUnknownReason])

  const multi = cameraOk && faceSim === 'multi'
  const searching = cameraOk && faceSim === 'notfound'
  const tone = !cameraOk ? 'error' : multi ? 'warn' : 'normal'

  return (
    <div className="flex h-full w-full flex-col bg-brand-50">
      <TopBar onExit={() => endSession('manual')} exitLabel="ยกเลิก" />
      <OfflineBanner />

      {/* ---- ภาพจำลองจากกล้อง ---- */}
      <div className="relative flex-1 overflow-hidden bg-[#0C1A13]">
        {cameraOk ? (
          <>
            <div
              className="absolute inset-0 opacity-70"
              style={{
                background:
                  'radial-gradient(circle at 50% 42%, #24493A 0%, #14291F 45%, #0A1611 100%)',
              }}
            />
            {/* เส้นตารางบาง ๆ แทนภาพวิดีโอ (ไม่ใช้ blur เพื่อความลื่นบน Raspberry Pi) */}
            <div
              className="absolute inset-0 opacity-15"
              style={{
                backgroundImage:
                  'linear-gradient(#9FD8BA 1px, transparent 1px), linear-gradient(90deg, #9FD8BA 1px, transparent 1px)',
                backgroundSize: '60px 60px',
              }}
            />

            <FaceGuide tone={tone} />

            {!multi ? (
              <div className="absolute left-1/2 top-[calc(50%-280px)] h-1 w-[420px] -translate-x-1/2 bg-brand-300/80 animate-scan-line" />
            ) : null}

            {multi ? (
              <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 px-12">
                <div className="rounded-[28px] border-2 border-alert-100 bg-alert-50 px-10 py-12 text-center">
                  <IconUsers className="mx-auto h-24 w-24 text-alert-700" />
                  <p className="mt-6 text-h2 font-bold text-alert-900">กรุณาใช้งานทีละคน</p>
                  <p className="mt-4 text-body-lg text-alert-900/90">
                    ระบบตรวจพบมากกว่าหนึ่งใบหน้า จึงยังไม่แสดงข้อมูลใด ๆ
                  </p>
                </div>
              </div>
            ) : null}
          </>
        ) : (
          /* ---- กล้องใช้งานไม่ได้ ---- */
          <div className="flex h-full flex-col items-center justify-center px-12 text-center">
            <IconCameraOff className="h-[140px] w-[140px] text-danger-100" />
            <p className="mt-10 text-h2 font-bold text-white">กล้องใช้งานไม่ได้ในขณะนี้</p>
            <p className="mt-5 max-w-[760px] text-body-lg text-white/75">
              ระบบกำลังเปลี่ยนไปใช้การกรอกรหัสนักศึกษาแทนโดยอัตโนมัติ
            </p>
            <div className="mt-10 flex items-center gap-4 text-label text-white/60">
              <span className="h-10 w-10 rounded-full border-4 border-white/25 border-t-white/80 animate-spin-slow" />
              กำลังเปลี่ยนวิธียืนยันตัวตน…
            </div>
          </div>
        )}
      </div>

      {/* ---- แถบสถานะ + ทางเลือกสำรอง ---- */}
      <div className="bg-white px-12 py-10">
        {cameraOk && !multi ? (
          <div className="flex items-center justify-center gap-5">
            <span className="flex gap-2">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="h-4 w-4 rounded-full bg-brand-600 animate-dot"
                  style={{ animationDelay: `${i * 180}ms` }}
                />
              ))}
            </span>
            <p className="text-h3 font-bold text-brand-900">กำลังตรวจจับใบหน้า…</p>
          </div>
        ) : null}

        {searching ? (
          <p className="mt-5 text-center text-body text-ink-soft">
            ขยับเข้าใกล้ตู้เล็กน้อย และมองตรงมาที่กรอบ ({Math.min(elapsed, 10)}/10 วินาที)
          </p>
        ) : null}

        {multi ? (
          <div className="flex items-center justify-center gap-4">
            <IconWarning className="h-10 w-10 text-alert-700" />
            <p className="text-h3 font-bold text-alert-900">พบหลายใบหน้า · หยุดตรวจจับชั่วคราว</p>
          </div>
        ) : null}

        {cameraOk ? (
          <Button
            variant="secondary"
            size="lg"
            icon={IconKeypad}
            className="mt-8 w-full"
            onClick={() => {
              markActivity()
              setUnknownReason('manual')
              goto('keypad')
            }}
          >
            กรอกรหัสนักศึกษาแทน
          </Button>
        ) : null}
      </div>
    </div>
  )
}
