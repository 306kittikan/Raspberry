import React from 'react'
import { useKiosk } from '../state/KioskProvider'
import TopBar from '../components/TopBar'
import OfflineBanner from '../components/OfflineBanner'
import ChatWindow from '../components/ChatWindow'
import { Button, UpdatedAt } from '../components/ui'
import { IconArrowLeft, IconFace } from '../components/Icons'

/**
 * หน้าผู้ช่วยตอบคำถาม — เป็นหน้าต่างแชทเต็มรูปแบบ
 *
 * ตัวหน้าต่างอยู่ใน components/ChatWindow.jsx ทั้งหมด
 * หน้านี้เหลือแค่แถบบน แถบออฟไลน์ และปุ่มกลับ ซึ่งเป็นส่วนของตู้ ไม่ใช่ของแชท
 */
export default function AssistantScreen() {
  const { student, hasSchedule, goto, endSession, startScan } = useKiosk()

  return (
    <div className="flex h-full w-full flex-col bg-brand-50">
      <TopBar
        showName={Boolean(student)}
        onExit={() => endSession('manual')}
        exitLabel={student ? 'ออกจากระบบ' : 'จบการใช้งาน'}
      />
      <OfflineBanner />

      <div className="min-h-0 flex-1 px-10 pb-5 pt-6">
        <ChatWindow />
      </div>

      <div className="shrink-0 border-t-2 border-brand-100 bg-white px-12 py-6">
        {student ? (
          <>
            <Button
              size="lg"
              variant="secondary"
              icon={IconArrowLeft}
              className="w-full"
              onClick={() => goto('home')}
            >
              กลับหน้าตารางเรียนของฉัน
            </Button>
            {hasSchedule ? <UpdatedAt className="mt-4 text-center" /> : null}
          </>
        ) : (
          <Button size="lg" icon={IconFace} className="w-full" onClick={startScan}>
            ยืนยันตัวตนเพื่อดูตารางเรียนของคุณ
          </Button>
        )}
      </div>
    </div>
  )
}
