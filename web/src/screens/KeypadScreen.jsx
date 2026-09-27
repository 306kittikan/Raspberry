import React, { useRef, useState } from 'react'
import { useKiosk } from '../state/KioskProvider'
import Keypad from '../components/Keypad'
import TopBar from '../components/TopBar'
import OfflineBanner from '../components/OfflineBanner'
import { Button } from '../components/ui'
import { IconCameraOff, IconIncognito } from '../components/Icons'

/** หน้ากรอกรหัสนักศึกษาด้วยแป้นตัวเลขบนจอ */
export default function KeypadScreen() {
  const {
    loginWithStudentId,
    startAnonymous,
    endSession,
    unknownReason,
    markActivity,
    enrollIntent,
    pendingToken,
    completeEnroll,
    loginError,
  } = useKiosk()

  // มีใบหน้าที่ถ่ายไว้รออยู่ = หน้านี้คือขั้นสุดท้ายของการลงทะเบียน
  // ไม่ใช่การเข้าสู่ระบบธรรมดา
  const finishingEnroll = Boolean(pendingToken)
  const [value, setValue] = useState('')
  const [error, setError] = useState('')
  const [checking, setChecking] = useState(false)

  // loginError ถูกตั้งค่าระหว่าง await จึงยังไม่ทันเข้ามาในรอบเรนเดอร์นี้
  // เก็บไว้ใน ref เพื่ออ่านค่าล่าสุดได้ทันทีหลังคำขอจบ
  const loginErrorRef = useRef(loginError)
  loginErrorRef.current = loginError

  // loginWithStudentId คืน Promise ต้องรอผลจริง
  // ไม่งั้นค่าที่ได้เป็น Promise ซึ่งเป็นจริงเสมอ และข้อความผิดพลาดจะไม่ขึ้นเลย
  const submit = async () => {
    if (checking) return
    setChecking(true)
    const ok = finishingEnroll
      ? await completeEnroll(value)
      : await loginWithStudentId(value)
    setChecking(false)
    if (!ok) {
      // ใช้ข้อความจากเซิร์ฟเวอร์ เพราะสาเหตุต่างกัน (ไม่มีรหัสนี้ / พ้นสภาพแล้ว)
      setError(loginErrorRef.current || 'ไม่พบรหัสนักศึกษานี้ในระบบ กรุณาตรวจสอบอีกครั้ง')
      setValue('')
    }
  }

  return (
    <div className="flex h-full w-full flex-col bg-brand-50">
      <TopBar onExit={() => endSession('manual')} exitLabel="ยกเลิก" />
      <OfflineBanner />

      {unknownReason === 'camera' ? (
        <div className="flex items-center gap-4 border-b-2 border-alert-100 bg-alert-50 px-12 py-5">
          <IconCameraOff className="h-9 w-9 shrink-0 text-alert-700" />
          <p className="text-label leading-snug text-alert-900">
            กล้องใช้งานไม่ได้ ระบบจึงเปลี่ยนมาใช้การกรอกรหัสนักศึกษาโดยอัตโนมัติ
          </p>
        </div>
      ) : null}

      <div className="flex flex-1 flex-col px-12 py-10">
        <h1 className="text-h2 font-bold text-brand-900">
          {finishingEnroll ? 'ใบหน้านี้เป็นของใคร' : 'กรอกรหัสนักศึกษา'}
        </h1>
        <p className="mt-3 text-body text-ink-soft">
          {finishingEnroll
            ? 'ถ่ายใบหน้าเรียบร้อยแล้ว เหลือเพียงกรอกรหัสนักศึกษาเพื่อผูกข้อมูลเข้าด้วยกัน'
            : 'ตัวเลขที่กรอกไปแล้วจะถูกปิดบัง เพื่อความเป็นส่วนตัวขณะยืนใช้งาน'}
        </p>

        <div className="mt-10 flex flex-1 flex-col justify-center">
          <Keypad
            value={value}
            onChange={(v) => {
              markActivity()
              setError('')
              setValue(v)
            }}
            onSubmit={submit}
            error={error}
          />
        </div>

        <Button
          variant="secondary"
          size="lg"
          icon={IconIncognito}
          className="mt-6 w-full"
          onClick={startAnonymous}
        >
          ใช้งานแบบไม่ระบุตัวตน
        </Button>
      </div>
    </div>
  )
}
