import React, { useEffect, useState } from 'react'
import { useKiosk } from '../state/KioskProvider'
import { formatClock, formatThaiDate } from '../lib/time'
import { Button } from '../components/ui'
import OfflineBanner from '../components/OfflineBanner'
import { IconBell, IconFace, IconIncognito, IconLogo } from '../components/Icons'

/**
 * หน้าจอพัก — ยังไม่ยืนยันตัวตน จึงต้องไม่แสดงข้อมูลส่วนบุคคลใด ๆ
 */
export default function IdleScreen() {
  const { now, startScan, startAnonymous, department, announcements, termLabel } = useKiosk()
  const [annIndex, setAnnIndex] = useState(0)

  // ประกาศมาจากเซิร์ฟเวอร์ จึงยังว่างอยู่ในเฟรมแรก และจำนวนเปลี่ยนได้ระหว่างวัน
  useEffect(() => {
    setAnnIndex(0)
    if (announcements.length < 2) return undefined
    const id = setInterval(() => {
      setAnnIndex((i) => (i + 1) % announcements.length)
    }, 6000)
    return () => clearInterval(id)
  }, [announcements])

  const ann = announcements[annIndex] ?? null

  return (
    <div className="flex h-full w-full flex-col bg-brand-50">
      <OfflineBanner />

      {/* ---- ส่วนหัว: เวลา วันที่ ชื่อสาขา ---- */}
      <div className="bg-brand-800 px-12 pb-12 pt-14 text-white">
        <div className="flex items-center gap-5">
          <IconLogo className="h-[76px] w-[76px] text-brand-200" />
          <div>
            <p className="text-h3 font-bold leading-tight">{department?.name}</p>
            <p className="text-label text-brand-100">{department?.faculty}</p>
          </div>
        </div>

        <p className="mt-10 text-mega font-bold leading-none tabular-nums">{formatClock(now)}</p>
        <p className="mt-3 text-h3 text-brand-100">{formatThaiDate(now)}</p>
        <p className="mt-2 text-label text-brand-200">{termLabel}</p>
      </div>

      {/* ---- คำเชิญชวนหลัก ---- */}
      <div className="flex flex-1 flex-col justify-between px-12 py-12">
        <div className="card flex flex-col items-center px-10 py-14 text-center">
          <span className="relative flex h-[200px] w-[200px] items-center justify-center">
            <span className="absolute inset-0 rounded-full border-4 border-brand-300 animate-pulse-ring" />
            <span className="flex h-[200px] w-[200px] items-center justify-center rounded-full border-4 border-brand-600 bg-brand-50">
              <IconFace className="h-[110px] w-[110px] text-brand-700" />
            </span>
          </span>

          <h1 className="mt-10 text-h1 font-bold leading-tight text-brand-900">
            ยืนหน้าตู้เพื่อดูตารางเรียนของคุณ
          </h1>
          <p className="mt-5 max-w-[800px] text-body-lg text-ink-soft">
            ระบบจะยืนยันตัวตนด้วยใบหน้าโดยอัตโนมัติ ไม่ต้องพิมพ์ข้อความใด ๆ
          </p>
        </div>

        {/* ---- ประกาศของสาขา วนแสดงอัตโนมัติ (ซ่อนเมื่อยังไม่มีประกาศ) ---- */}
        <div className={`card mt-8 p-9 ${ann ? '' : 'hidden'}`}>
          <div className="flex items-center gap-4">
            <IconBell className="h-10 w-10 text-brand-700" />
            <p className="text-label font-bold text-brand-800">ประกาศของสาขา</p>
            <span className="ml-auto flex gap-2">
              {announcements.map((a, i) => (
                <span
                  key={a.id}
                  className={`h-3 rounded-full transition-all duration-200 ${
                    i === annIndex ? 'w-10 bg-brand-600' : 'w-3 bg-brand-200'
                  }`}
                />
              ))}
            </span>
          </div>

          <div key={ann?.id} className="mt-6 animate-fade-in">
            <span className="inline-block rounded-full bg-brand-100 px-5 py-2 text-[22px] font-semibold text-brand-800">
              {ann?.tag}
            </span>
            <p className="mt-4 text-h3 font-bold leading-snug text-brand-900">{ann?.title}</p>
            <p className="mt-2 text-body text-ink-soft">{ann?.detail}</p>
          </div>
        </div>

        {/* ---- ปุ่มหลัก วางช่วงกลางถึงล่างของจอ ---- */}
        <div className="mt-8 flex flex-col gap-5">
          <Button size="xl" icon={IconFace} onClick={startScan}>
            เริ่มสแกนใบหน้า
          </Button>
          <Button size="lg" variant="secondary" icon={IconIncognito} onClick={startAnonymous}>
            ถามคำถามโดยไม่ระบุตัวตน
          </Button>
        </div>
      </div>
    </div>
  )
}
