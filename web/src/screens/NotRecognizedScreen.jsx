import React from 'react'
import { useKiosk } from '../state/KioskProvider'
import { Button } from '../components/ui'
import TopBar from '../components/TopBar'
import OfflineBanner from '../components/OfflineBanner'
import {
  IconArrowRight,
  IconCameraOff,
  IconFace,
  IconIncognito,
  IconKeypad,
  IconWarning,
} from '../components/Icons'

const HEADINGS = {
  inactive: {
    icon: IconWarning,
    title: 'รหัสนักศึกษานี้ไม่ได้อยู่ในสถานะกำลังศึกษา',
    detail: 'กรุณาติดต่อสำนักงานสาขาวิชาฯ เพื่อตรวจสอบสถานะของคุณ',
  },
  unrecognized: {
    icon: IconWarning,
    title: 'ระบบยังจำใบหน้าของคุณไม่ได้',
    detail: 'เลือกวิธีใช้งานต่อไปนี้ได้เลย',
  },
  timeout: {
    icon: IconFace,
    title: 'หาใบหน้าไม่พบ',
    detail: 'ระบบค้นหาใบหน้าเกิน 10 วินาทีแล้ว ลองใช้วิธีอื่นแทนได้',
  },
  camera: {
    icon: IconCameraOff,
    title: 'กล้องใช้งานไม่ได้',
    detail: 'กรุณายืนยันตัวตนด้วยรหัสนักศึกษา หรือใช้งานแบบไม่ระบุตัวตน',
  },
}

function OptionCard({ icon: Icon, title, detail, onClick, primary }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`press tap flex w-full items-center gap-8 rounded-[28px] border-2 px-10 py-9 text-left ${
        primary
          ? 'border-brand-700 bg-brand-700 text-white active:bg-brand-800'
          : 'border-brand-200 bg-white text-brand-900 active:bg-brand-50'
      }`}
    >
      <span
        className={`flex h-[96px] w-[96px] shrink-0 items-center justify-center rounded-3xl ${
          primary ? 'bg-white/15' : 'bg-brand-100'
        }`}
      >
        <Icon className={`h-14 w-14 ${primary ? 'text-white' : 'text-brand-700'}`} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-h3 font-bold leading-tight">{title}</span>
        <span
          className={`mt-2 block text-body leading-snug ${primary ? 'text-brand-100' : 'text-ink-soft'}`}
        >
          {detail}
        </span>
      </span>
      <IconArrowRight className={`h-12 w-12 shrink-0 ${primary ? 'text-white' : 'text-brand-400'}`} />
    </button>
  )
}

/** หน้าจำไม่ได้ — ยังไม่ยืนยันตัวตน จึงไม่แสดงข้อมูลส่วนบุคคลใด ๆ */
export default function NotRecognizedScreen() {
  const { unknownReason, goto, startEnrollFlow, startAnonymous, startScan, endSession } =
    useKiosk()
  const head = HEADINGS[unknownReason] || HEADINGS.unrecognized
  const Icon = head.icon
  const canEnroll = unknownReason !== 'timeout' && unknownReason !== 'camera'

  return (
    <div className="flex h-full w-full flex-col bg-brand-50">
      <TopBar onExit={() => endSession('manual')} exitLabel="ยกเลิก" />
      <OfflineBanner />

      <div className="flex flex-1 flex-col justify-between px-12 py-12">
        <div className="card px-10 py-12 text-center">
          <span className="mx-auto flex h-[140px] w-[140px] items-center justify-center rounded-full bg-alert-50">
            <Icon className="h-20 w-20 text-alert-700" />
          </span>
          <h1 className="mt-8 text-h2 font-bold text-brand-900">{head.title}</h1>
          <p className="mt-4 text-body-lg text-ink-soft">{head.detail}</p>
        </div>

        <div className="mt-10 flex flex-col gap-5">
          {canEnroll ? (
            <OptionCard
              primary
              icon={IconFace}
              title="ลงทะเบียนใบหน้า"
              detail="กรอกรหัสนักศึกษาหนึ่งครั้ง แล้วครั้งต่อไปยืนหน้าตู้ได้เลย"
              onClick={startEnrollFlow}
            />
          ) : null}

          <OptionCard
            icon={IconKeypad}
            title="กรอกรหัสนักศึกษา"
            detail="ใช้แป้นตัวเลขบนหน้าจอ ไม่ต้องใช้กล้อง"
            onClick={() => goto('keypad')}
          />

          <OptionCard
            icon={IconIncognito}
            title="ใช้งานแบบไม่ระบุตัวตน"
            detail="ถามข้อมูลทั่วไปของสาขาได้ แต่จะไม่เห็นตารางเรียนส่วนบุคคล"
            onClick={startAnonymous}
          />
        </div>

        <div className="mt-10">
          <Button variant="ghost" size="md" className="w-full" onClick={startScan}>
            ลองสแกนใบหน้าอีกครั้ง
          </Button>
        </div>
      </div>
    </div>
  )
}
