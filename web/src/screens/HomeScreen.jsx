import React, { useState } from 'react'
import { useKiosk } from '../state/KioskProvider'
import TopBar from '../components/TopBar'
import OfflineBanner from '../components/OfflineBanner'
import SourceBadge from '../components/SourceBadge'
import { Button, EmptyState, UpdatedAt } from '../components/ui'
import {
  IconCalendar,
  IconClock,
  IconFace,
  IconPin,
  IconSparkle,
  IconWarning,
} from '../components/Icons'
import { formatCountdown } from '../lib/time'
import { CHANNEL, SOURCE } from '../lib/logger'

/** ชื่อวันตามเลขวันแบบ ISO (1 = จันทร์) ซึ่งเป็นรูปแบบที่เซิร์ฟเวอร์ส่งมา */
const DAY_NAMES = { 1: 'จันทร์', 2: 'อังคาร', 3: 'พุธ', 4: 'พฤหัสบดี', 5: 'ศุกร์' }

/** เลขวันของวันนี้แบบ ISO — Date.getDay() ให้อาทิตย์ = 0 แต่ ISO ให้อาทิตย์ = 7 */
const isoDay = (d) => d.getDay() || 7

const TABS = [
  { id: 'today', label: 'วันนี้' },
  { id: 'week', label: 'ทั้งสัปดาห์' },
  { id: 'exam', label: 'กำหนดสอบ' },
]

function ClassRow({ item, muted }) {
  return (
    <div
      className={`flex items-stretch gap-6 rounded-xl3 bg-white px-8 py-7 ring-1 ${
        muted ? 'ring-brand-100' : 'ring-brand-200'
      }`}
    >
      <div className="flex w-[150px] shrink-0 flex-col justify-center border-r-2 border-brand-100 pr-6">
        <p className="text-[30px] font-bold tabular-nums leading-tight text-brand-800">
          {item.start}
        </p>
        <p className="text-label tabular-nums text-ink-mute">{item.end}</p>
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[24px] font-semibold text-ink-mute">{item.code}</p>
        <p className="truncate text-h3 font-bold leading-tight text-brand-900">{item.name}</p>
        <p className="mt-2 text-body text-ink-soft">
          {/* ห้องของคณะอื่นมีแค่ชื่อ ไม่รู้ชั้นและอาคาร
              แสดงเท่าที่รู้ ดีกว่าขึ้นว่า "ชั้น null" หรือเดาเลขชั้นขึ้นมา */}
          ห้อง {item.room ?? '—'}
          {item.floor ? ` · ชั้น ${item.floor}` : null}
          {item.building ? ` ${item.building}` : null}
        </p>
      </div>
    </div>
  )
}

export default function HomeScreen() {
  const {
    now, hasSchedule, schedule, exams, department,
    faceEnrolled, startEnrollFlow, goto, endSession, track,
  } = useKiosk()
  const [tab, setTab] = useState('today')

  // ตารางเรียน คาบถัดไป และการนับถอยหลังทั้งหมดคำนวณที่เซิร์ฟเวอร์
  // ฝั่งนี้เหลือเพียงแปลงเวลาเป็น Date เพื่อให้ตัวเลขนับถอยหลังเดินทุกวินาที
  const { today, week } = schedule
  const raw = schedule.nextClass
  const next = raw
    ? { ...raw, start: new Date(raw.startISO), end: new Date(raw.endISO) }
    : null

  const selectTab = (id) => {
    setTab(id)
    track(`ดูตาราง: ${TABS.find((t) => t.id === id).label}`, CHANNEL.TOUCH, SOURCE.DB)
  }

  return (
    <div className="stage-surface flex h-full w-full flex-col">
      <TopBar showName onExit={() => endSession('manual')} />
      <OfflineBanner />

      <div className="min-h-0 flex-1 overflow-y-auto px-12 pb-6 pt-8">
        {/* ---- ชวนลงทะเบียนใบหน้า เฉพาะคนที่ยังไม่เคยลงทะเบียน ---- */}
        {!faceEnrolled ? (
          <button
            type="button"
            onClick={startEnrollFlow}
            className="press tap card mb-7 flex w-full items-center gap-5 px-8 py-6 text-left active:bg-brand-50"
          >
            <IconFace className="h-14 w-14 shrink-0 text-brand-700" />
            <span className="min-w-0 flex-1">
              <span className="block text-[26px] font-bold leading-tight text-brand-900">
                ลงทะเบียนใบหน้าไว้ไหม
              </span>
              <span className="mt-1 block text-body leading-snug text-ink-soft">
                ครั้งต่อไปยืนหน้าตู้แล้วเห็นตารางเรียนได้เลย ไม่ต้องกรอกรหัส
              </span>
            </span>
          </button>
        ) : null}

        {/* ---- วิชาถัดไป: เด่นที่สุดบนหน้าจอ ---- */}
        {!hasSchedule ? (
          <>
            <EmptyState
              icon={IconWarning}
              title="ยังไม่มีข้อมูลตารางเรียนภาคการศึกษานี้"
              detail={`กรุณาติดต่อสำนักงานสาขา · ${department?.officeLocation ?? ''} ${department?.officeHours ?? ''}`}
            />
            <div className="mt-7 flex items-center justify-between">
              <UpdatedAt />
              <SourceBadge source="db" />
            </div>
          </>
        ) : next ? (
          <div className="rounded-xl4 bg-gradient-to-br from-brand-700 via-brand-800 to-brand-900 p-10 text-white shadow-hero">
            <div className="flex items-center gap-4">
              <IconClock className="h-9 w-9 text-brand-200" />
              <p className="text-label font-semibold text-brand-100">
                {next.ongoing
                  ? 'กำลังเรียนอยู่ตอนนี้'
                  : `วิชาถัดไป · ${next.dayLabel}`}
              </p>
            </div>

            <p className="mt-5 text-[26px] font-semibold text-brand-200">{next.item.code}</p>
            <h1 className="mt-1 text-h1 font-bold leading-tight">{next.item.name}</h1>

            <div className="mt-8 grid grid-cols-2 gap-6">
              <div className="rounded-[22px] bg-white/10 px-7 py-6">
                <p className="text-label text-brand-100">เวลาเรียน</p>
                <p className="mt-1 text-h3 font-bold tabular-nums">
                  {next.item.start}–{next.item.end} น.
                </p>
              </div>
              <div className="rounded-[22px] bg-white/10 px-7 py-6">
                <p className="flex items-center gap-2 text-label text-brand-100">
                  <IconPin className="h-7 w-7" /> ห้องเรียน
                </p>
                <p className="mt-1 text-h3 font-bold">
                  {next.item.room} · ชั้น {next.item.floor}
                </p>
              </div>
            </div>

            <div className="mt-6 rounded-[22px] bg-white/15 px-7 py-6 text-center ring-1 ring-white/25">
              <p className="text-label text-white/85">
                {next.ongoing ? 'เลิกเรียน' : 'นับถอยหลังถึงเวลาเรียน'}
              </p>
              <p className="mt-1 text-h2 font-bold">
                {formatCountdown((next.ongoing ? next.end : next.start) - now)}
              </p>
            </div>

            <SourceBadge source="db" className="mt-8 bg-white" />
          </div>
        ) : (
          <EmptyState
            icon={IconCalendar}
            title="ไม่พบคาบเรียนถัดไป"
            detail="ตารางเรียนของคุณไม่มีคาบเรียนในสัปดาห์นี้"
          />
        )}

        {/* ---- แท็บ (ซ่อนเมื่อไม่มีข้อมูลตารางเรียน) ---- */}
        <div
          className={`stage-surface sticky top-0 z-10 -mx-12 mt-9 px-12 pb-5 pt-2 ${
            hasSchedule ? '' : 'hidden'
          }`}
        >
          <div className="segment grid grid-cols-3 gap-2">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                data-on={tab === t.id}
                onClick={() => selectTab(t.id)}
                className="press segment-item min-h-[84px]"
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* ---- เนื้อหาตามแท็บ ---- */}
        {hasSchedule ? (
          <div className="space-y-5">
            {tab === 'today' ? (
              today.length > 0 ? (
                today.map((item) => (
                  <ClassRow key={`${item.day}-${item.start}-${item.code}`} item={item} />
                ))
              ) : (
                <EmptyState
                  icon={IconCalendar}
                  title="วันนี้ไม่มีคาบเรียน"
                  detail={
                    next
                      ? `คาบถัดไปคือ ${next.item.name} ${next.dayLabel} เวลา ${next.item.start} น. ห้อง ${next.item.room}`
                      : 'ไม่พบคาบเรียนถัดไปในตารางของคุณ'
                  }
                />
              )
            ) : null}

            {tab === 'week'
              ? Object.entries(week).map(([day, items]) => (
                  <div key={day}>
                    <p className="mb-3 mt-2 text-[26px] font-bold text-brand-800">
                      วัน{DAY_NAMES[day]}
                      {Number(day) === isoDay(now) ? (
                        <span className="ml-3 rounded-full bg-brand-600 px-4 py-1 text-[20px] font-semibold text-white">
                          วันนี้
                        </span>
                      ) : null}
                    </p>
                    {items.length > 0 ? (
                      <div className="space-y-4">
                        {items.map((item) => (
                          <ClassRow key={`${item.day}-${item.start}-${item.code}`} item={item} muted />
                        ))}
                      </div>
                    ) : (
                      <p className="rounded-[20px] border-2 border-dashed border-brand-200 bg-white px-8 py-6 text-body text-ink-mute">
                        ไม่มีคาบเรียน
                      </p>
                    )}
                  </div>
                ))
              : null}

            {tab === 'exam' ? (
              exams.length > 0 ? (
                exams.map((exam) => (
                  <div
                    key={exam.code}
                    className="rounded-[24px] border-2 border-brand-200 bg-white px-8 py-7"
                  >
                    <div className="flex items-center gap-4">
                      <span className="rounded-full bg-alert-50 px-5 py-2 text-[22px] font-semibold text-alert-700">
                        {exam.type}
                      </span>
                      <span className="text-[24px] font-semibold text-ink-mute">{exam.code}</span>
                    </div>
                    <p className="mt-3 text-h3 font-bold leading-tight text-brand-900">
                      {exam.name}
                    </p>
                    <p className="mt-3 text-body text-ink-soft">
                      {exam.dateLabel} · เวลา {exam.time} น.
                    </p>
                    <p className="text-body text-ink-soft">ห้องสอบ {exam.room}</p>
                  </div>
                ))
              ) : (
                <EmptyState
                  icon={IconCalendar}
                  title="ยังไม่มีกำหนดสอบ"
                  detail="ยังไม่มีประกาศกำหนดสอบในภาคการศึกษานี้ ติดตามประกาศจากสำนักงานสาขาวิชาฯ อีกครั้ง"
                />
              )
            ) : null}

            <div className="flex items-center justify-between pt-3">
              <UpdatedAt />
              <SourceBadge source="db" />
            </div>
          </div>
        ) : null}
      </div>

      {/* ---- ปุ่มหลักช่วงล่างของจอ ---- */}
      <div className="border-t-2 border-brand-100 bg-white px-12 py-7">
        <div className="grid grid-cols-2 gap-5">
          <Button size="lg" icon={IconSparkle} onClick={() => goto('assistant')}>
            ถามผู้ช่วย
          </Button>
          <Button
            size="lg"
            variant="secondary"
            icon={IconFace}
            onClick={faceEnrolled ? () => goto('facedata') : startEnrollFlow}
          >
            {faceEnrolled ? 'จัดการข้อมูลใบหน้า' : 'ลงทะเบียนใบหน้า'}
          </Button>
        </div>
      </div>
    </div>
  )
}
