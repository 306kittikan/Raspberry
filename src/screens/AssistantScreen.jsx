import React from 'react'
import { useKiosk } from '../state/KioskProvider'
import TopBar from '../components/TopBar'
import OfflineBanner from '../components/OfflineBanner'
import MicPanel from '../components/MicPanel'
import AnswerCard from '../components/AnswerCard'
import { Button, UpdatedAt } from '../components/ui'
import SourceBadge from '../components/SourceBadge'
import {
  IconArrowLeft,
  IconDatabase,
  IconIncognito,
  IconSparkle,
  IconFace,
} from '../components/Icons'
import { QUICK_QUESTIONS } from '../data/mockData'
import { CHANNEL } from '../lib/logger'

export default function AssistantScreen() {
  const {
    student,
    anonymous,
    online,
    answer,
    answerPending,
    askQuestion,
    goto,
    endSession,
    startScan,
  } = useKiosk()

  return (
    <div className="flex h-full w-full flex-col bg-brand-50">
      <TopBar
        showName={Boolean(student)}
        onExit={() => endSession('manual')}
        exitLabel={student ? 'ออกจากระบบ' : 'จบการใช้งาน'}
      />
      <OfflineBanner />

      {anonymous && !student ? (
        <div className="flex items-center gap-4 border-b-2 border-brand-100 bg-white px-12 py-5">
          <IconIncognito className="h-9 w-9 shrink-0 text-brand-700" />
          <p className="text-label leading-snug text-ink-soft">
            <span className="font-semibold text-brand-800">โหมดไม่ระบุตัวตน</span> — ตอบคำถามทั่วไปของสาขาได้
            แต่จะไม่แสดงตารางเรียนหรือข้อมูลส่วนบุคคล
          </p>
        </div>
      ) : null}

      <div className="min-h-0 flex-1 overflow-y-auto px-12 pb-6 pt-8">
        <h1 className="text-h2 font-bold text-brand-900">ผู้ช่วยตอบคำถาม</h1>
        <p className="mt-3 text-body text-ink-soft">
          พูดถามหรือแตะเลือกคำถามด้านล่างก็ได้ ทุกคำตอบจะบอกที่มาของข้อมูลเสมอ
        </p>

        <div className="mt-8">
          <MicPanel />
        </div>

        {/* ---- พื้นที่แสดงคำตอบ ---- */}
        {answer || answerPending ? (
          <div className="mt-8">
            <AnswerCard answer={answer} pending={answerPending} />
          </div>
        ) : null}

        {/* ---- คำถามยอดนิยมแบบแตะได้ ---- */}
        <div className="mt-9">
          <div className="mb-5 flex items-center gap-4">
            <h2 className="text-h3 font-bold text-brand-900">คำถามยอดนิยม</h2>
            <span className="flex items-center gap-2 text-[21px] text-ink-mute">
              <IconDatabase className="h-6 w-6 text-brand-600" /> ฐานข้อมูล
              <IconSparkle className="ml-3 h-6 w-6 text-ai-600" /> AI
            </span>
          </div>

          <div className="grid grid-cols-2 gap-5">
            {QUICK_QUESTIONS.map((q) => {
              const aiBlocked = q.source === 'ai' && !online
              const needAuth = q.personal && !student
              const Icon = q.source === 'ai' ? IconSparkle : IconDatabase

              return (
                <button
                  key={q.id}
                  type="button"
                  disabled={aiBlocked}
                  onClick={() => askQuestion(q.id, CHANNEL.TOUCH)}
                  className={`press tap flex min-h-[132px] flex-col justify-center rounded-[24px] border-2 px-8 py-6 text-left ${
                    aiBlocked
                      ? 'border-brand-200 bg-brand-100 text-ink-soft'
                      : q.source === 'ai'
                        ? 'border-ai-100 bg-ai-50 text-ai-900 active:bg-ai-100'
                        : 'border-brand-200 bg-white text-brand-900 active:bg-brand-100'
                  }`}
                >
                  <span className="flex items-center gap-3">
                    <Icon
                      className={`h-8 w-8 shrink-0 ${
                        aiBlocked ? 'text-ink-soft' : q.source === 'ai' ? 'text-ai-600' : 'text-brand-600'
                      }`}
                    />
                    <span className="text-body font-semibold leading-snug">{q.label}</span>
                  </span>

                  {aiBlocked ? (
                    <span className="mt-3 text-[21px] leading-snug">
                      ใช้ไม่ได้ขณะออฟไลน์ — ต้องเชื่อมต่ออินเทอร์เน็ต
                    </span>
                  ) : needAuth ? (
                    <span className="mt-3 text-[21px] leading-snug text-ink-mute">
                      ต้องยืนยันตัวตนก่อน
                    </span>
                  ) : null}
                </button>
              )
            })}
          </div>
        </div>

        <div className="mt-8 flex items-center justify-between">
          <UpdatedAt />
          <SourceBadge source="db" />
        </div>
      </div>

      <div className="border-t-2 border-brand-100 bg-white px-12 py-7">
        {student ? (
          <Button size="lg" variant="secondary" icon={IconArrowLeft} className="w-full" onClick={() => goto('home')}>
            กลับหน้าตารางเรียนของฉัน
          </Button>
        ) : (
          <Button size="lg" icon={IconFace} className="w-full" onClick={startScan}>
            ยืนยันตัวตนเพื่อดูตารางเรียนของคุณ
          </Button>
        )}
      </div>
    </div>
  )
}
