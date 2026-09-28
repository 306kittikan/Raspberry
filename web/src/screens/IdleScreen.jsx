import React, { useEffect, useState } from 'react'
import { useKiosk } from '../state/KioskProvider'
import { formatClock, formatThaiDate } from '../lib/time'
import { Button } from '../components/ui'
import OfflineBanner from '../components/OfflineBanner'
import { IconBell, IconFace, IconIncognito, IconKeypad } from '../components/Icons'
import Logo from '../components/Logo'

/**
 * หน้าจอพัก — ยังไม่ยืนยันตัวตน จึงต้องไม่แสดงข้อมูลส่วนบุคคลใด ๆ
 */
export default function IdleScreen() {
  const { now, startScan, startAnonymous, goto, department, announcements, termLabel } = useKiosk()
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
    <div className="stage-surface flex h-full w-full flex-col">
      <OfflineBanner />

      {/* ---- ส่วนหัว: เวลา วันที่ ชื่อสาขา ---- */}
      {/* ไล่สีทแยงแทนสีเขียวทึบ และลบมุมล่างให้โค้ง
          ขอบตรงเป็นเส้นแบ่งแข็ง ๆ ทำให้ส่วนหัวดูเหมือนแถบที่แปะทับ
          ไม่ใช่พื้นผิวที่ต่อเนื่องกับเนื้อหาข้างล่าง */}
      <div className="relative overflow-hidden rounded-b-[40px] bg-white px-12 pb-8 pt-9 shadow-card-lg">
        {/* แถบฟ้าอ่อนจางหายไปทางล่าง ให้ส่วนหัวมีมิติโดยไม่ทับโลโก้
            เป็นไล่สีธรรมดา ไม่ใช่การเบลอ จึงไม่กินแรงเครื่องบน Pi */}
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-[420px]"
          style={{
            background:
              'radial-gradient(120% 100% at 80% 0%, rgba(127, 184, 238, 0.28) 0%, rgba(127, 184, 238, 0.10) 40%, rgba(127, 184, 238, 0) 72%)',
          }}
        />

        {/* โลโก้มีชื่อสาขาเป็นภาษาอังกฤษอยู่ในภาพแล้ว จึงไม่ต้องมีบรรทัดชื่อสาขาซ้ำ
            เหลือไว้แต่ชื่อคณะเป็นภาษาไทย ซึ่งโลโก้ไม่ได้บอกและนักศึกษาไทยอ่านได้ทันที */}
        <div className="relative">
          <Logo height={112} />
          {/* โลโก้บอกชื่อสาขาเป็นภาษาอังกฤษเท่านั้น
              นักศึกษาไทยกวาดสายตาหาข้อความภาษาไทยก่อนเสมอ
              จึงต้องมีชื่อสาขาภาษาไทยอยู่ด้วย ไม่ใช่มีแต่ชื่อคณะ */}
          <p className="mt-4 text-label font-semibold text-ink-soft">
            {department?.name} · {department?.faculty}
          </p>
        </div>

        <p className="relative mt-7 text-mega font-bold leading-none tracking-tight tabular-nums text-brand-800">
          {formatClock(now)}
        </p>
        <p className="relative mt-2 text-h3 font-semibold text-brand-700">{formatThaiDate(now)}</p>
        <p className="relative mt-2 text-label text-ink-mute">{termLabel}</p>
      </div>

      {/* ---- คำเชิญชวนหลัก ---- */}
      <div className="flex min-h-0 flex-1 flex-col justify-between px-12 py-7">
        <div className="card flex flex-col items-center px-10 py-9 text-center">
          <span className="relative flex h-[184px] w-[184px] items-center justify-center">
            <span className="absolute inset-0 rounded-full border-4 border-brand-300 animate-pulse-ring" />
            <span className="flex h-[184px] w-[184px] items-center justify-center rounded-full bg-gradient-to-br from-brand-50 to-brand-100 shadow-card ring-2 ring-brand-300">
              <IconFace className="h-[100px] w-[100px] text-brand-700" />
            </span>
          </span>

          <h1 className="mt-6 text-h1 font-bold leading-tight text-brand-900">
            ยืนหน้าตู้เพื่อดูตารางเรียนของคุณ
          </h1>
          <p className="mt-4 max-w-[800px] text-body-lg text-ink-soft">
            ระบบจะยืนยันตัวตนด้วยใบหน้าโดยอัตโนมัติ ไม่ต้องพิมพ์ข้อความใด ๆ
          </p>
        </div>

        {/* ---- ประกาศของสาขา วนแสดงอัตโนมัติ (ซ่อนเมื่อยังไม่มีประกาศ) ---- */}
        <div className={`card mt-6 p-8 ${ann ? '' : 'hidden'}`}>
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
            <span className="inline-block rounded-full bg-brand-100 px-5 py-2 text-[22px] font-semibold text-brand-800 ring-1 ring-brand-200">
              {ann?.tag}
            </span>
            <p className="mt-4 text-h3 font-bold leading-snug text-brand-900">{ann?.title}</p>
            <p className="mt-2 text-body text-ink-soft">{ann?.detail}</p>
          </div>
        </div>

        {/* ---- ปุ่มหลัก วางช่วงกลางถึงล่างของจอ ---- */}
        <div className="mt-6 flex flex-col gap-4">
          <Button size="xl" icon={IconFace} onClick={startScan}>
            เริ่มสแกนใบหน้า
          </Button>
          {/* เดิมต้องเข้าหน้าสแกนก่อนถึงจะไปกรอกรหัสได้
              คนที่ไม่อยากให้ตู้สแกนหน้าจึงต้องกดผ่านหน้าที่เปิดกล้องอยู่ดี
              ซึ่งขัดกับเจตนาของเขา จึงต้องมีทางเข้าตรงจากหน้าแรก */}
          <Button size="lg" variant="secondary" icon={IconKeypad} onClick={() => goto('keypad')}>
            กรอกรหัสนักศึกษาแทน
          </Button>
          <Button size="lg" variant="ghost" icon={IconIncognito} onClick={startAnonymous}>
            ถามคำถามโดยไม่ระบุตัวตน
          </Button>
        </div>
      </div>
    </div>
  )
}
