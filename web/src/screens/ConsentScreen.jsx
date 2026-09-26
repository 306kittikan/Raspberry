import React, { useState } from 'react'
import { useKiosk } from '../state/KioskProvider'
import { Button } from '../components/ui'
import TopBar from '../components/TopBar'
import OfflineBanner from '../components/OfflineBanner'
import { IconCheck, IconShield, IconTrash, IconFace } from '../components/Icons'

const POINTS = [
  {
    icon: IconFace,
    title: 'ระบบไม่เก็บภาพใบหน้าของคุณ',
    detail: 'ภาพจากกล้องถูกประมวลผลบนตู้แล้วลบทิ้งทันที ไม่มีการบันทึกเป็นไฟล์ภาพ',
  },
  {
    icon: IconShield,
    title: 'เก็บเฉพาะค่าเวกเตอร์ใบหน้า',
    detail: 'เป็นชุดตัวเลขที่ใช้เทียบว่าเป็นคุณหรือไม่ ไม่สามารถย้อนกลับเป็นภาพใบหน้าได้',
  },
  {
    icon: IconTrash,
    title: 'ลบข้อมูลของตนเองได้ทุกเมื่อ',
    detail: 'กดลบได้เองจากหน้าหลัก ที่เมนู “จัดการข้อมูลใบหน้า” โดยไม่ต้องติดต่อเจ้าหน้าที่',
  },
]

/** หน้าขอความยินยอม — ช่องทำเครื่องหมายต้องแตะเอง ห้ามทำเครื่องหมายไว้ล่วงหน้า */
export default function ConsentScreen() {
  const [agreed, setAgreed] = useState(false)
  const { startEnrollCapture, endSession, goto, markActivity } = useKiosk()

  return (
    <div className="flex h-full w-full flex-col bg-brand-50">
      <TopBar onExit={() => endSession('manual')} exitLabel="ยกเลิก" />
      <OfflineBanner />

      <div className="flex flex-1 flex-col px-12 py-10">
        <h1 className="text-h2 font-bold text-brand-900">ลงทะเบียนใบหน้า</h1>
        <p className="mt-3 text-body-lg text-ink-soft">
          ก่อนเริ่ม กรุณาอ่านและให้ความยินยอมในการเก็บข้อมูล
        </p>

        <div className="mt-9 space-y-5">
          {POINTS.map((p) => {
            const Icon = p.icon
            return (
              <div key={p.title} className="card flex items-start gap-7 p-9">
                <span className="flex h-[88px] w-[88px] shrink-0 items-center justify-center rounded-3xl bg-brand-100">
                  <Icon className="h-12 w-12 text-brand-700" />
                </span>
                <span>
                  <span className="block text-h3 font-bold leading-tight text-brand-900">
                    {p.title}
                  </span>
                  <span className="mt-2 block text-body leading-snug text-ink-soft">{p.detail}</span>
                </span>
              </div>
            )
          })}
        </div>

        {/* ---- ช่องยินยอม: ค่าเริ่มต้นไม่ติ๊ก ต้องแตะเอง ---- */}
        <button
          type="button"
          onClick={() => {
            markActivity()
            setAgreed((v) => !v)
          }}
          className={`press mt-9 flex w-full items-center gap-7 rounded-[28px] border-4 px-9 py-8 text-left ${
            agreed ? 'border-brand-600 bg-brand-100' : 'border-brand-300 bg-white'
          }`}
        >
          <span
            className={`flex h-[80px] w-[80px] shrink-0 items-center justify-center rounded-2xl border-4 ${
              agreed ? 'border-brand-700 bg-brand-700' : 'border-brand-400 bg-white'
            }`}
          >
            {agreed ? <IconCheck className="h-12 w-12 text-white" strokeWidth={3} /> : null}
          </span>
          <span className="text-body-lg font-semibold leading-snug text-brand-900">
            ข้าพเจ้ายินยอมให้สาขาวิชาฯ จัดเก็บค่าเวกเตอร์ใบหน้าเพื่อใช้ยืนยันตัวตนกับตู้บริการนี้
          </span>
        </button>

        <div className="mt-auto flex flex-col gap-5 pt-10">
          <Button size="xl" disabled={!agreed} onClick={startEnrollCapture}>
            {agreed ? 'เริ่มถ่ายใบหน้า' : 'กรุณาแตะช่องยินยอมก่อน'}
          </Button>
          <Button size="lg" variant="secondary" onClick={() => goto('unknown')}>
            ย้อนกลับ
          </Button>
        </div>
      </div>
    </div>
  )
}
