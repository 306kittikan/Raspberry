import React from 'react'
import { useKiosk } from '../state/KioskProvider'
import { Button } from './ui'
import { IconClock } from './Icons'

/**
 * ไม่มีการใช้งาน 30 วินาที → นับถอยหลังออกจากระบบ 10 วินาที
 * กด "ยังใช้งานอยู่" เพื่ออยู่ต่อ หรือ "ออกจากระบบตอนนี้" เพื่อจบทันที
 */
export default function InactivityOverlay() {
  const { logoutCountdown, markActivity, endSession } = useKiosk()
  if (logoutCountdown === null) return null

  return (
    <div className="absolute inset-0 z-40 flex items-center justify-center bg-brand-900/95 px-16 animate-fade-in">
      <div className="w-full rounded-[36px] bg-white px-14 py-16 text-center">
        <IconClock className="mx-auto h-24 w-24 text-alert-700" />
        <p className="mt-8 text-h2 font-bold text-brand-900">
          จะออกจากระบบใน {logoutCountdown} วินาที
        </p>
        <p className="mt-5 text-body-lg text-ink-soft">
          เพื่อความเป็นส่วนตัว ระบบจะล้างข้อมูลบนหน้าจอทั้งหมดเมื่อไม่มีการใช้งาน
        </p>

        <div className="mt-12 flex flex-col gap-5">
          <Button size="xl" onClick={markActivity}>
            ยังใช้งานอยู่
          </Button>
          <Button size="lg" variant="secondary" onClick={() => endSession('manual')}>
            ออกจากระบบตอนนี้
          </Button>
        </div>
      </div>
    </div>
  )
}
