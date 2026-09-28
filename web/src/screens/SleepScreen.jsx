import React from 'react'
import { useKiosk } from '../state/KioskProvider'
import { formatClock, formatThaiDate } from '../lib/time'
import { IconLogo } from '../components/Icons'

/**
 * จอพักลึก — ไม่มีคนเกิน 2 นาที
 * หรี่จอเหลือเพียงนาฬิกาและโลโก้บนพื้นมืด
 * แตะหรือเซ็นเซอร์ตรวจพบคน → ตื่นกลับสู่หน้าจอพักทันที
 */
export default function SleepScreen() {
  const { now, detectPresence, department } = useKiosk()

  return (
    <div
      onClick={detectPresence}
      className="flex h-full w-full flex-col items-center justify-center bg-[#04101B] text-center animate-fade-in"
    >
      <IconLogo className="h-[180px] w-[180px] text-brand-500/40" />

      <p className="mt-16 text-clock font-bold tabular-nums text-white/35">{formatClock(now)}</p>

      <p className="mt-6 text-h3 text-white/20">{formatThaiDate(now)}</p>

      <p className="mt-24 text-label tracking-wide text-white/15">{department?.name}</p>
    </div>
  )
}
