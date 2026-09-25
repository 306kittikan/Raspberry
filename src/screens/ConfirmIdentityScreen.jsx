import React from 'react'
import { useKiosk } from '../state/KioskProvider'
import { Button } from '../components/ui'
import TopBar from '../components/TopBar'
import OfflineBanner from '../components/OfflineBanner'
import { IconCheck, IconClose, IconFace } from '../components/Icons'

/**
 * หน้ายืนยันตัวตน — แสดงเฉพาะชื่อ ไม่แสดงรหัสนักศึกษา
 * เพราะยังไม่ได้ยืนยันว่าเป็นเจ้าของข้อมูลจริง
 */
export default function ConfirmIdentityScreen() {
  const { candidate, confirmCandidate, endSession } = useKiosk()

  return (
    <div className="flex h-full w-full flex-col bg-brand-50">
      <TopBar onExit={() => endSession('manual')} exitLabel="ยกเลิก" />
      <OfflineBanner />

      <div className="flex flex-1 flex-col justify-between px-12 py-14">
        <div className="card flex flex-col items-center px-10 py-16 text-center">
          <span className="flex h-[220px] w-[220px] items-center justify-center rounded-full border-4 border-brand-600 bg-brand-100">
            <IconFace className="h-[120px] w-[120px] text-brand-700" />
          </span>

          <p className="mt-12 text-h3 text-ink-soft">ระบบจำใบหน้าได้แล้ว</p>
          <h1 className="mt-4 text-h1 font-bold leading-tight text-brand-900">
            คุณคือ {candidate ? candidate.name : '—'} ใช่ไหม
          </h1>
          <p className="mt-6 max-w-[780px] text-body text-ink-mute">
            ระบบจะแสดงตารางเรียนของคุณหลังจากกดยืนยัน
          </p>
        </div>

        <div className="mt-10 grid grid-cols-2 gap-6">
          <Button size="xl" icon={IconCheck} onClick={() => confirmCandidate(true)}>
            ใช่
          </Button>
          <Button size="xl" variant="secondary" icon={IconClose} onClick={() => confirmCandidate(false)}>
            ไม่ใช่
          </Button>
        </div>
      </div>
    </div>
  )
}
