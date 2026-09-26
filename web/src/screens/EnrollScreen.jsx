import React from 'react'
import { useKiosk } from '../state/KioskProvider'
import { Button } from '../components/ui'
import TopBar from '../components/TopBar'
import { IconCheck, IconFace } from '../components/Icons'

const STEPS = [
  { at: 0, label: 'มองตรงมาที่กล้อง' },
  { at: 34, label: 'หันหน้าไปทางซ้ายเล็กน้อย' },
  { at: 67, label: 'หันหน้าไปทางขวาเล็กน้อย' },
]

/** ขั้นตอนถ่ายใบหน้า พร้อมตัวบอกความคืบหน้า */
export default function EnrollScreen() {
  const { enrollProgress, finishEnroll, endSession } = useKiosk()
  const done = enrollProgress >= 100
  const current = [...STEPS].reverse().find((s) => enrollProgress >= s.at)

  return (
    <div className="flex h-full w-full flex-col bg-brand-50">
      <TopBar onExit={() => endSession('manual')} exitLabel="ยกเลิก" />

      <div className="flex flex-1 flex-col justify-between px-12 py-12">
        <div className="card flex flex-col items-center px-10 py-14 text-center">
          <span
            className={`flex h-[240px] w-[240px] items-center justify-center rounded-full border-4 ${
              done ? 'border-brand-600 bg-brand-100' : 'border-brand-300 bg-brand-50'
            }`}
          >
            {done ? (
              <IconCheck className="h-[120px] w-[120px] text-brand-700" strokeWidth={3} />
            ) : (
              <IconFace className="h-[130px] w-[130px] text-brand-600" />
            )}
          </span>

          <h1 className="mt-10 text-h2 font-bold text-brand-900">
            {done ? 'ลงทะเบียนใบหน้าสำเร็จ' : 'กำลังถ่ายใบหน้า'}
          </h1>
          <p className="mt-4 text-body-lg text-ink-soft">
            {done ? 'ครั้งต่อไปคุณจะเข้าใช้งานได้ทันทีเมื่อยืนหน้าตู้' : current?.label}
          </p>

          {/* ---- ตัวบอกความคืบหน้า ---- */}
          <div className="mt-12 w-full">
            <div className="h-8 w-full overflow-hidden rounded-full bg-brand-100">
              <div
                className="h-full rounded-full bg-brand-600 transition-[width] duration-150 ease-linear"
                style={{ width: `${enrollProgress}%` }}
              />
            </div>
            <p className="mt-4 text-h3 font-bold tabular-nums text-brand-800">{enrollProgress}%</p>
          </div>

          <div className="mt-10 flex w-full justify-between gap-4">
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

        <div className="mt-10">
          <Button size="xl" className="w-full" disabled={!done} onClick={finishEnroll}>
            {done ? 'เข้าสู่ตารางเรียนของฉัน' : 'กรุณารอสักครู่…'}
          </Button>
        </div>
      </div>
    </div>
  )
}
