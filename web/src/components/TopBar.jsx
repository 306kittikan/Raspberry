import React from 'react'
import { useKiosk } from '../state/KioskProvider'
import { formatClock } from '../lib/time'
import { IconLogo, IconLogout, IconWifiOff } from './Icons'

/**
 * แถบบนสุด: โลโก้ + ชื่อสาขา + เวลา + ปุ่มออกจากระบบ (มองเห็นได้ตลอดทุกหน้า)
 * ไม่แสดงรหัสนักศึกษาเต็ม เพราะคนเดินผ่านมองเห็นจอได้
 */
export default function TopBar({ onExit, exitLabel = 'ออกจากระบบ', showName = false }) {
  const { now, student, online, department } = useKiosk()

  return (
    <header className="relative z-10 flex items-center gap-6 bg-white px-12 py-6 shadow-card">
      <IconLogo className="h-[72px] w-[72px] shrink-0 text-brand-700" />

      <div className="min-w-0 flex-1">
        <p className="truncate text-[28px] font-bold leading-tight text-brand-900">
          {showName && student ? student.name : department?.name}
        </p>
        <p className="truncate text-[22px] leading-tight text-ink-mute">
          {showName && student
            ? `รหัส ${student.studentIdMasked} · ชั้นปีที่ ${student.year}`
            : department?.faculty}
        </p>
      </div>

      {!online ? (
        <span className="flex items-center gap-2 rounded-full bg-alert-50 px-5 py-3 text-[22px] font-semibold text-alert-700 ring-1 ring-alert-700/30">
          <IconWifiOff className="h-7 w-7" />
          ออฟไลน์
        </span>
      ) : null}

      <span className="text-[40px] font-bold tabular-nums text-brand-800">{formatClock(now)}</span>

      {onExit ? (
        <button
          type="button"
          onClick={onExit}
          className="press tap inline-flex items-center gap-3 rounded-xl2 bg-brand-50 px-7 py-4 text-label font-semibold text-brand-800 ring-1 ring-brand-200/70 active:bg-brand-100"
        >
          <IconLogout className="h-9 w-9" />
          {exitLabel}
        </button>
      ) : null}
    </header>
  )
}
