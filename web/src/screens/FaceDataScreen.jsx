import React, { useState } from 'react'
import { useKiosk } from '../state/KioskProvider'
import TopBar from '../components/TopBar'
import OfflineBanner from '../components/OfflineBanner'
import { Button } from '../components/ui'
import {
  IconArrowLeft,
  IconCheck,
  IconFace,
  IconShield,
  IconTrash,
  IconWarning,
} from '../components/Icons'

/** หน้าจัดการข้อมูลใบหน้า: ดู → ยืนยันก่อนลบ → ยืนยันหลังลบเสร็จ */
export default function FaceDataScreen() {
  const { faceEnrolled, faceEnrolledAtLabel, canDeleteFace, startEnrollFlow, deleteFaceData, goto, endSession } =
    useKiosk()
  const [step, setStep] = useState('view') // view | confirm | deleted

  const doDelete = () => {
    deleteFaceData()
    setStep('deleted')
  }

  return (
    <div className="flex h-full w-full flex-col bg-brand-50">
      <TopBar showName onExit={() => endSession('manual')} />
      <OfflineBanner />

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-12 py-10">
        {step === 'view' ? (
          <>
            <h1 className="text-h2 font-bold text-brand-900">จัดการข้อมูลใบหน้า</h1>
            <p className="mt-3 text-body text-ink-soft">
              คุณเป็นเจ้าของข้อมูลนี้ และลบได้ด้วยตนเองทุกเมื่อ
            </p>

            <div className="card mt-8 p-10">
              <div className="flex items-center gap-7">
                <span
                  className={`flex h-[110px] w-[110px] shrink-0 items-center justify-center rounded-3xl ${
                    faceEnrolled ? 'bg-brand-100' : 'bg-brand-50'
                  }`}
                >
                  <IconFace
                    className={`h-16 w-16 ${faceEnrolled ? 'text-brand-700' : 'text-ink-mute'}`}
                  />
                </span>
                <div>
                  <p className="text-h3 font-bold text-brand-900">
                    {faceEnrolled ? 'มีข้อมูลใบหน้าในระบบ' : 'ไม่มีข้อมูลใบหน้าในระบบ'}
                  </p>
                  <p className="mt-2 text-body text-ink-soft">
                    {faceEnrolled
                      ? `ลงทะเบียนเมื่อ ${faceEnrolledAtLabel ?? 'ไม่ทราบวันที่'}`
                      : 'ครั้งต่อไปต้องยืนยันตัวตนด้วยรหัสนักศึกษา'}
                  </p>
                </div>
              </div>

              <div className="mt-8 rounded-[24px] border-2 border-brand-100 bg-brand-50 p-8">
                <p className="flex items-center gap-3 text-label font-bold text-brand-800">
                  <IconShield className="h-8 w-8" /> ระบบเก็บอะไรไว้บ้าง
                </p>
                <ul className="mt-4 space-y-3 text-body text-ink-soft">
                  <li>· ค่าเวกเตอร์ใบหน้า (ชุดตัวเลข) ใช้เทียบตัวตนเท่านั้น</li>
                  <li>· ไม่มีการเก็บภาพใบหน้าหรือวิดีโอจากกล้อง</li>
                  <li>· ไม่มีการส่งข้อมูลใบหน้าออกนอกระบบของสาขา</li>
                </ul>
              </div>
            </div>

            <div className="mt-auto flex flex-col gap-5 pt-10">
              <Button
                size="xl"
                variant="outlineDanger"
                icon={IconTrash}
                disabled={!faceEnrolled || !canDeleteFace}
                onClick={() => setStep('confirm')}
              >
                ลบข้อมูลใบหน้าของฉัน
              </Button>
              <Button size="lg" variant="secondary" icon={IconArrowLeft} onClick={() => goto('home')}>
                กลับหน้าหลัก
              </Button>
            </div>
          </>
        ) : null}

        {step === 'confirm' ? (
          <>
            <div className="card flex flex-col items-center px-10 py-14 text-center">
              <span className="flex h-[150px] w-[150px] items-center justify-center rounded-full bg-danger-50">
                <IconWarning className="h-[84px] w-[84px] text-danger-600" />
              </span>
              <h1 className="mt-9 text-h2 font-bold text-brand-900">ยืนยันการลบข้อมูลใบหน้า</h1>
              <p className="mt-5 max-w-[780px] text-body-lg text-ink-soft">
                หลังลบแล้วจะกู้คืนไม่ได้ และครั้งต่อไปต้องยืนยันตัวตนด้วยรหัสนักศึกษา
                หรือลงทะเบียนใบหน้าใหม่อีกครั้ง
              </p>
              <p className="mt-6 text-body text-ink-mute">
                ตารางเรียนและข้อมูลการศึกษาของคุณจะไม่ถูกลบ
              </p>
            </div>

            <div className="mt-auto flex flex-col gap-5 pt-10">
              <Button size="xl" variant="danger" icon={IconTrash} onClick={doDelete}>
                ยืนยันลบข้อมูลใบหน้า
              </Button>
              <Button size="lg" variant="secondary" onClick={() => setStep('view')}>
                ยกเลิก
              </Button>
            </div>
          </>
        ) : null}

        {step === 'deleted' ? (
          <>
            <div className="card flex flex-col items-center px-10 py-14 text-center">
              <span className="flex h-[150px] w-[150px] items-center justify-center rounded-full bg-brand-100">
                <IconCheck className="h-[84px] w-[84px] text-brand-700" strokeWidth={3} />
              </span>
              <h1 className="mt-9 text-h2 font-bold text-brand-900">ลบข้อมูลใบหน้าเรียบร้อยแล้ว</h1>
              <p className="mt-5 max-w-[780px] text-body-lg text-ink-soft">
                ค่าเวกเตอร์ใบหน้าของคุณถูกลบออกจากระบบของสาขาแล้ว
              </p>
              <p className="mt-6 text-body text-ink-mute">
                ครั้งต่อไปกรุณาเข้าใช้งานด้วยรหัสนักศึกษา หรือลงทะเบียนใบหน้าใหม่ได้ที่ตู้บริการ
              </p>
            </div>

            <div className="mt-auto flex flex-col gap-5 pt-10">
              <Button size="xl" onClick={() => goto('home')}>
                กลับหน้าหลัก
              </Button>
              <Button size="lg" variant="secondary" onClick={() => endSession('manual')}>
                ออกจากระบบ
              </Button>
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
