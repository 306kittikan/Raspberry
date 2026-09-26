import React, { useMemo } from 'react'
import { useKiosk } from '../state/KioskProvider'
import * as api from '../lib/api'
import { Button } from '../components/ui'
import TopBar from '../components/TopBar'
import { IconCheck, IconFace, IconWarning } from '../components/Icons'

const STEPS = [
  { at: 0, label: 'มองตรงมาที่กล้อง' },
  { at: 34, label: 'หันหน้าไปทางซ้ายเล็กน้อย' },
  { at: 67, label: 'หันหน้าไปทางขวาเล็กน้อย' },
]

/** ข้อความอธิบายสาเหตุที่ลงทะเบียนไม่สำเร็จ ให้ผู้ใช้รู้ว่าต้องทำอะไรต่อ */
const FAILURES = {
  quality: {
    title: 'ภาพใบหน้าไม่สม่ำเสมอ',
    detail: 'ลองใหม่อีกครั้ง โดยมองตรงมาที่กล้องและอยู่ในที่ที่มีแสงพอ',
  },
  duplicate: {
    title: 'ใบหน้านี้ถูกลงทะเบียนไว้กับรหัสนักศึกษาอื่นแล้ว',
    detail: 'กรุณาติดต่อสำนักงานสาขาวิชาฯ เพื่อตรวจสอบข้อมูล',
  },
  consent: {
    title: 'ไม่พบความยินยอมที่ใช้งานได้',
    detail: 'กรุณาเริ่มขั้นตอนใหม่ตั้งแต่หน้าขอความยินยอม',
  },
}

/** ขั้นตอนถ่ายใบหน้า พร้อมตัวบอกความคืบหน้า */
export default function EnrollScreen() {
  const { enrollProgress, enrollError, cameraReady, finishEnroll, cancelEnroll, goto, endSession } =
    useKiosk()
  const done = enrollProgress >= 100 && !enrollError
  const current = [...STEPS].reverse().find((s) => enrollProgress >= s.at)
  const failure = enrollError
    ? FAILURES[enrollError] ?? { title: 'ลงทะเบียนใบหน้าไม่สำเร็จ', detail: enrollError }
    : null

  // ให้ผู้ใช้เห็นภาพตัวเองระหว่างถ่าย จะได้จัดท่าทางได้ถูก
  const streamUrl = useMemo(() => api.cameraStreamUrl(), [])

  return (
    <div className="flex h-full w-full flex-col bg-brand-50">
      <TopBar onExit={() => endSession('manual')} exitLabel="ยกเลิก" />

      <div className="flex flex-1 flex-col justify-between px-12 py-12">
        <div className="card flex flex-col items-center px-10 py-14 text-center">
          <span
            className={`relative flex h-[240px] w-[240px] items-center justify-center overflow-hidden rounded-full border-4 ${
              failure
                ? 'border-danger-600 bg-danger-50'
                : done
                  ? 'border-brand-600 bg-brand-100'
                  : 'border-brand-300 bg-brand-50'
            }`}
          >
            {failure ? (
              <IconWarning className="h-[120px] w-[120px] text-danger-600" />
            ) : done ? (
              <IconCheck className="h-[120px] w-[120px] text-brand-700" strokeWidth={3} />
            ) : cameraReady ? (
              <img src={streamUrl} alt="" className="h-full w-full scale-x-[-1] object-cover" />
            ) : (
              <IconFace className="h-[130px] w-[130px] text-brand-600" />
            )}
          </span>

          <h1 className="mt-10 text-h2 font-bold text-brand-900">
            {failure ? failure.title : done ? 'ลงทะเบียนใบหน้าสำเร็จ' : 'กำลังถ่ายใบหน้า'}
          </h1>
          <p className="mt-4 text-body-lg text-ink-soft">
            {failure
              ? failure.detail
              : done
                ? 'ครั้งต่อไปคุณจะเข้าใช้งานได้ทันทีเมื่อยืนหน้าตู้'
                : current?.label}
          </p>

          {/* ---- ตัวบอกความคืบหน้า ---- */}
          <div className={`mt-12 w-full ${failure ? 'hidden' : ''}`}>
            <div className="h-8 w-full overflow-hidden rounded-full bg-brand-100">
              <div
                className="h-full rounded-full bg-brand-600 transition-[width] duration-150 ease-linear"
                style={{ width: `${enrollProgress}%` }}
              />
            </div>
            <p className="mt-4 text-h3 font-bold tabular-nums text-brand-800">{enrollProgress}%</p>
          </div>

          <div className={`mt-10 flex w-full justify-between gap-4 ${failure ? 'hidden' : ''}`}>
            {STEPS.map((s) => (
              <div
                key={s.label}
                className={`flex-1 rounded-2xl border-2 px-4 py-5 text-[21px] font-semibold leading-tight ${
                  enrollProgress > s.at + 32
                    ? 'border-brand-600 bg-brand-100 text-brand-800'
                    : enrollProgress >= s.at
                      ? 'border-brand-400 bg-white text-brand-700'
                      : 'border-brand-100 bg-white text-ink-mute'
                }`}
              >
                {s.label}
              </div>
            ))}
          </div>
        </div>

        <div className="mt-10 flex flex-col gap-5">
          {failure ? (
            <>
              <Button
                size="xl"
                className="w-full"
                onClick={() => {
                  cancelEnroll()
                  goto('consent')
                }}
              >
                ลองใหม่อีกครั้ง
              </Button>
              <Button
                size="lg"
                variant="secondary"
                className="w-full"
                onClick={() => endSession('manual')}
              >
                ยกเลิก
              </Button>
            </>
          ) : (
            <Button size="xl" className="w-full" disabled={!done} onClick={finishEnroll}>
              {done ? 'เข้าสู่ตารางเรียนของฉัน' : 'กรุณารอสักครู่…'}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
