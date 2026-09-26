import React from 'react'
import { useKiosk } from '../state/KioskProvider'
import { IconClose, IconSettings } from './Icons'

function SimButton({ children, onClick, tone = 'default' }) {
  const tones = {
    default: 'border-white/25 bg-white/10 text-white active:bg-white/20',
    on: 'border-brand-300 bg-brand-500 text-white active:bg-brand-600',
    warn: 'border-alert-100 bg-alert-700 text-white active:bg-alert-900',
  }
  return (
    <button
      type="button"
      onClick={onClick}
      className={`press min-h-[72px] rounded-2xl border-2 px-4 text-[21px] font-semibold leading-tight ${tones[tone]}`}
    >
      {children}
    </button>
  )
}

function Group({ title, children }) {
  return (
    <div className="mb-7">
      <p className="mb-3 text-[20px] font-bold uppercase tracking-wide text-white/50">{title}</p>
      <div className="grid grid-cols-2 gap-3">{children}</div>
    </div>
  )
}

/** แผงตัวควบคุมทดสอบ (ซ่อนได้) — สำหรับสาธิตสถานะต่าง ๆ โดยไม่ต้องต่ออุปกรณ์จริง */
export default function DevPanel() {
  const {
    devOpen,
    setDevOpen,
    sim,
    online,
    hasSchedule,
    cameraOk,
    activeStudentIdx,
    activeStudent,
    simStudents,
    events,
    screen,
  } = useKiosk()

  if (!devOpen) {
    return (
      // แถบเรียกแผงทดสอบ: ซ่อนไว้ที่ขอบขวาในระยะขอบของเนื้อหา ไม่ทับปุ่มใด ๆ
      <button
        type="button"
        onClick={() => setDevOpen(true)}
        aria-label="เปิดแผงตัวควบคุมทดสอบ"
        className="press absolute right-0 top-1/2 z-50 flex h-[140px] w-[44px] -translate-y-1/2 items-center justify-center rounded-l-2xl bg-brand-900/25 text-white/70 active:bg-brand-900/60"
      >
        <IconSettings className="h-8 w-8" />
      </button>
    )
  }

  return (
    <aside className="absolute inset-y-0 right-0 z-50 flex w-[560px] flex-col bg-brand-900 px-8 py-8 text-white shadow-2xl animate-fade-in">
      <div className="mb-7 flex items-center justify-between">
        <div>
          <p className="text-[30px] font-bold">แผงตัวควบคุมทดสอบ</p>
          <p className="text-[20px] text-white/60">หน้าจอปัจจุบัน: {screen}</p>
        </div>
        <button
          type="button"
          onClick={() => setDevOpen(false)}
          aria-label="ปิดแผงตัวควบคุมทดสอบ"
          className="press tap flex h-[72px] w-[72px] items-center justify-center rounded-full border-2 border-white/25 active:bg-white/15"
        >
          <IconClose className="h-9 w-9" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        <Group title="เซ็นเซอร์ตรวจจับคน">
          <SimButton onClick={sim.presence} tone="on">
            ตรวจพบคน (ปลุกจอ)
          </SimButton>
          <SimButton onClick={sim.sleep}>เข้าสู่จอพักลึก</SimButton>
        </Group>

        <Group title="การรู้จำใบหน้า">
          <SimButton onClick={sim.recognized} tone="on">
            จำหน้าได้
          </SimButton>
          <SimButton onClick={sim.unrecognized}>จำหน้าไม่ได้</SimButton>
          <SimButton onClick={sim.multiFace} tone="warn">
            พบหลายใบหน้า
          </SimButton>
          <SimButton onClick={sim.noFace} tone="warn">
            หาใบหน้าไม่เจอ
          </SimButton>
          <SimButton onClick={sim.cameraDown} tone={cameraOk ? 'warn' : 'on'}>
            กล้องใช้งานไม่ได้
          </SimButton>
          <SimButton onClick={() => sim.setActiveStudentIdx((activeStudentIdx + 1) % Math.max(1, simStudents.length))}>
            สลับผู้ใช้: {activeStudent?.name ?? '—'}
          </SimButton>
        </Group>

        <Group title="เครือข่าย">
          <SimButton onClick={() => sim.setOnline(true)} tone={online ? 'on' : 'default'}>
            ออนไลน์
          </SimButton>
          <SimButton onClick={() => sim.setOnline(false)} tone={!online ? 'warn' : 'default'}>
            ออฟไลน์
          </SimButton>
        </Group>

        <Group title="เสียง">
          <SimButton onClick={sim.listening} tone="on">
            กำลังฟังเสียง
          </SimButton>
          <SimButton onClick={sim.unclear} tone="warn">
            ฟังไม่ชัด
          </SimButton>
        </Group>

        <Group title="ข้อมูล">
          <SimButton
            onClick={() => sim.setHasSchedule(!hasSchedule)}
            tone={hasSchedule ? 'default' : 'warn'}
          >
            {hasSchedule ? 'ไม่มีข้อมูลตารางเรียน' : 'คืนข้อมูลตารางเรียน'}
          </SimButton>
          <SimButton onClick={sim.reset}>รีเซ็ตทั้งหมด</SimButton>
        </Group>

        <div>
          <p className="mb-3 text-[20px] font-bold uppercase tracking-wide text-white/50">
            บันทึกการใช้งานล่าสุด (console)
          </p>
          {events.length === 0 ? (
            <p className="text-[20px] text-white/45">ยังไม่มีเหตุการณ์</p>
          ) : (
            <ul className="space-y-2">
              {events.map((e) => (
                <li
                  key={e.id}
                  className="rounded-xl border border-white/15 bg-black/25 px-4 py-3 text-[19px] leading-snug text-white/85"
                >
                  <span className="tabular-nums text-white/55">{e.time}</span> · {e.kind} ·{' '}
                  {e.channel} · {e.source}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </aside>
  )
}
