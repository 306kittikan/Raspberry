import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { STUDENTS, VOICE_SAMPLES } from '../data/mockData'
import { CHANNEL, SOURCE, logEvent } from '../lib/logger'
import { UNCLEAR_ANSWER, getQuestion, resolveAnswer } from '../lib/answers'

// ------------------------------------------------------------
// ค่าคงที่ของพฤติกรรมตู้
// ------------------------------------------------------------
export const TIMING = {
  SLEEP_AFTER_MS: 120_000, // ไม่มีคนเกิน 2 นาที → จอพักลึก
  IDLE_LOGOUT_MS: 30_000, // ไม่มีการใช้งาน 30 วินาที → เตือน
  LOGOUT_COUNTDOWN_S: 10, // นับถอยหลัง 10 วินาที ก่อนออกจากระบบ
  FACE_DETECT_MS: 2_600, // เวลาจำลองการตรวจจับใบหน้า
  FACE_TIMEOUT_MS: 10_000, // หาใบหน้าไม่เจอเกิน 10 วินาที
  VOICE_LISTEN_MS: 2_200,
  VOICE_PROCESS_MS: 1_200,
}

/** หน้าจอที่ถือว่าอยู่ใน "ช่วงใช้งาน" และต้องนับเวลาไม่ใช้งาน */
const SESSION_SCREENS = new Set([
  'confirm',
  'unknown',
  'keypad',
  'consent',
  'enroll',
  'home',
  'assistant',
  'facedata',
])

/** หน้าจอที่ผู้ใช้ยืนยันตัวตนแล้ว (แสดงข้อมูลส่วนบุคคลได้) */
const PRIVATE_SCREENS = new Set(['home', 'assistant', 'facedata'])

const KioskContext = createContext(null)

export function useKiosk() {
  const ctx = useContext(KioskContext)
  if (!ctx) throw new Error('useKiosk ต้องใช้ภายใน <KioskProvider>')
  return ctx
}

export function KioskProvider({ children }) {
  // ---- นาฬิกาเดินกลางตัวเดียวสำหรับทั้งแอป (ประหยัดทรัพยากรบน Raspberry Pi) ----
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  // ---- สถานะหลัก ----
  const [screen, setScreen] = useState('idle')
  const [student, setStudent] = useState(null)
  const [anonymous, setAnonymous] = useState(false)

  // ---- สถานะจำลองของอุปกรณ์/เครือข่าย ----
  const [online, setOnline] = useState(true)
  const [cameraOk, setCameraOk] = useState(true)
  const [hasSchedule, setHasSchedule] = useState(true)
  const [voiceUnclear, setVoiceUnclear] = useState(false)
  const [faceSim, setFaceSim] = useState('recognized') // recognized | unknown | multi | notfound
  const [activeStudentIdx, setActiveStudentIdx] = useState(0)
  const [deletedFaces, setDeletedFaces] = useState(() => new Set())

  // ---- สถานะย่อยของแต่ละหน้า ----
  const [unknownReason, setUnknownReason] = useState('unrecognized') // unrecognized | timeout | camera
  const [candidate, setCandidate] = useState(null) // ผู้ที่ระบบคิดว่าใช่ (ยังไม่ยืนยัน)
  const [micState, setMicState] = useState('idle') // idle | listening | processing
  const [transcript, setTranscript] = useState('')
  const [answer, setAnswer] = useState(null)
  const [answerPending, setAnswerPending] = useState(false)
  const [enrollProgress, setEnrollProgress] = useState(0)
  const [devOpen, setDevOpen] = useState(false)
  const [events, setEvents] = useState([])

  // ---- ตัวจับเวลา ----
  const [lastPresenceAt, setLastPresenceAt] = useState(() => Date.now())
  const [lastActivityAt, setLastActivityAt] = useState(() => Date.now())
  const [logoutCountdown, setLogoutCountdown] = useState(null)

  const timers = useRef([])
  const clearTimers = useCallback(() => {
    timers.current.forEach(clearTimeout)
    timers.current = []
  }, [])
  const later = useCallback((fn, ms) => {
    const id = setTimeout(fn, ms)
    timers.current.push(id)
    return id
  }, [])

  useEffect(() => () => clearTimers(), [clearTimers])

  // ------------------------------------------------------------
  // บันทึกเหตุการณ์ (ไม่มีข้อมูลระบุตัวตน)
  // ------------------------------------------------------------
  const track = useCallback((kind, channel, source) => {
    logEvent({ kind, channel, source })
    setEvents((prev) =>
      [
        {
          id: `${Date.now()}-${Math.random().toString(16).slice(2, 6)}`,
          time: new Date().toLocaleTimeString('th-TH', { hour12: false }),
          kind,
          channel,
          source,
        },
        ...prev,
      ].slice(0, 12)
    )
  }, [])

  // ------------------------------------------------------------
  // การแตะ/การมีตัวตนของผู้ใช้
  // ------------------------------------------------------------
  const markActivity = useCallback(() => {
    const t = Date.now()
    setLastActivityAt(t)
    setLastPresenceAt(t)
    setLogoutCountdown(null)
  }, [])

  /** เซ็นเซอร์ตรวจพบคน → ตื่นกลับสู่หน้าจอพักทันที */
  const detectPresence = useCallback(() => {
    setLastPresenceAt(Date.now())
    setScreen((s) => (s === 'sleep' ? 'idle' : s))
  }, [])

  // ------------------------------------------------------------
  // จบการใช้งาน: ล้างข้อมูลบนจอทั้งหมด
  // ------------------------------------------------------------
  const endSession = useCallback(
    (reason = 'manual') => {
      clearTimers()
      setStudent(null)
      setCandidate(null)
      setAnonymous(false)
      setMicState('idle')
      setTranscript('')
      setAnswer(null)
      setAnswerPending(false)
      setEnrollProgress(0)
      setLogoutCountdown(null)
      setUnknownReason('unrecognized')
      setScreen('idle')
      const t = Date.now()
      setLastActivityAt(t)
      setLastPresenceAt(t)
      if (reason === 'timeout') {
        // eslint-disable-next-line no-console
        console.log('[kiosk-session] ออกจากระบบอัตโนมัติเนื่องจากไม่มีการใช้งาน')
      }
    },
    [clearTimers]
  )

  // ------------------------------------------------------------
  // ตัวจับเวลา: จอพักลึก + ออกจากระบบอัตโนมัติ
  // ------------------------------------------------------------
  useEffect(() => {
    if (screen !== 'idle') return undefined
    const id = setInterval(() => {
      if (Date.now() - lastPresenceAt > TIMING.SLEEP_AFTER_MS) setScreen('sleep')
    }, 1000)
    return () => clearInterval(id)
  }, [screen, lastPresenceAt])

  useEffect(() => {
    if (!SESSION_SCREENS.has(screen)) return undefined
    const id = setInterval(() => {
      const elapsed = Date.now() - lastActivityAt
      if (elapsed > TIMING.IDLE_LOGOUT_MS) {
        const remain =
          TIMING.LOGOUT_COUNTDOWN_S -
          Math.floor((elapsed - TIMING.IDLE_LOGOUT_MS) / 1000)
        if (remain <= 0) endSession('timeout')
        else setLogoutCountdown(remain)
      }
    }, 250)
    return () => clearInterval(id)
  }, [screen, lastActivityAt, endSession])

  // ------------------------------------------------------------
  // การนำทาง
  // ------------------------------------------------------------
  const goto = useCallback(
    (next) => {
      markActivity()
      setScreen(next)
    },
    [markActivity]
  )

  const startScan = useCallback(() => {
    clearTimers()
    markActivity()
    setAnswer(null)
    setTranscript('')
    setScreen('scan')
  }, [clearTimers, markActivity])

  const confirmCandidate = useCallback(
    (yes) => {
      markActivity()
      if (yes && candidate) {
        setStudent(candidate)
        setAnonymous(false)
        setScreen('home')
        track('เข้าสู่ระบบด้วยใบหน้า', CHANNEL.TOUCH, SOURCE.DB)
      } else {
        setCandidate(null)
        setUnknownReason('unrecognized')
        setScreen('unknown')
      }
    },
    [candidate, markActivity, track]
  )

  const loginWithStudentId = useCallback(
    (id) => {
      markActivity()
      const found = STUDENTS.find((s) => s.studentId === id)
      if (!found) return false
      setStudent(found)
      setAnonymous(false)
      setScreen('home')
      track('เข้าสู่ระบบด้วยรหัสนักศึกษา', CHANNEL.TOUCH, SOURCE.DB)
      return true
    },
    [markActivity, track]
  )

  const startAnonymous = useCallback(() => {
    markActivity()
    setStudent(null)
    setAnonymous(true)
    setAnswer(null)
    setTranscript('')
    setScreen('assistant')
    track('ใช้งานแบบไม่ระบุตัวตน', CHANNEL.TOUCH, SOURCE.DB)
  }, [markActivity, track])

  // ------------------------------------------------------------
  // ลงทะเบียนใบหน้า
  // ------------------------------------------------------------
  const startEnrollCapture = useCallback(() => {
    markActivity()
    setEnrollProgress(0)
    setScreen('enroll')
    const step = () => {
      setEnrollProgress((p) => {
        if (p >= 100) return 100
        const next = Math.min(100, p + 4)
        if (next < 100) later(step, 140)
        return next
      })
    }
    later(step, 400)
  }, [later, markActivity])

  const finishEnroll = useCallback(() => {
    markActivity()
    const target = STUDENTS[activeStudentIdx]
    setDeletedFaces((prev) => {
      const next = new Set(prev)
      next.delete(target.id)
      return next
    })
    setStudent(target)
    setAnonymous(false)
    setScreen('home')
    track('ลงทะเบียนใบหน้าสำเร็จ', CHANNEL.TOUCH, SOURCE.DB)
  }, [activeStudentIdx, markActivity, track])

  const deleteFaceData = useCallback(() => {
    markActivity()
    if (!student) return
    setDeletedFaces((prev) => new Set(prev).add(student.id))
    track('ลบข้อมูลใบหน้า', CHANNEL.TOUCH, SOURCE.DB)
  }, [markActivity, student, track])

  // ------------------------------------------------------------
  // ถาม–ตอบ
  // ------------------------------------------------------------
  const askQuestion = useCallback(
    (questionId, channel = CHANNEL.TOUCH) => {
      markActivity()
      const q = getQuestion(questionId)
      if (!q) return
      setAnswerPending(true)
      setAnswer(null)
      later(() => {
        const result = resolveAnswer(questionId, { student, online, hasSchedule })
        setAnswer(result)
        setAnswerPending(false)
        const source =
          result.source === 'ai' ? SOURCE.AI : result.source === 'db' ? SOURCE.DB : SOURCE.AI
        track(q.kind, channel, source)
      }, 520)
    },
    [hasSchedule, later, markActivity, online, student, track]
  )

  const startListening = useCallback(() => {
    if (micState !== 'idle') return
    markActivity()
    setAnswer(null)
    setTranscript('')
    setMicState('listening')

    later(() => {
      if (voiceUnclear) {
        setMicState('idle')
        setAnswer(UNCLEAR_ANSWER)
        return
      }
      // เลือกประโยคจำลองที่เหมาะกับสถานะปัจจุบัน
      const pool = VOICE_SAMPLES.filter((v) => {
        const q = getQuestion(v.questionId)
        if (!q) return false
        if (q.personal && !student) return false
        return true
      })
      const pick = pool[Math.floor(Math.random() * pool.length)]
      setTranscript(pick.heard)
      setMicState('processing')

      later(() => {
        const result = resolveAnswer(pick.questionId, { student, online, hasSchedule })
        setAnswer(result)
        setMicState('idle')
        const q = getQuestion(pick.questionId)
        const source =
          result.source === 'ai' ? SOURCE.AI : result.source === 'db' ? SOURCE.DB : SOURCE.AI
        track(q.kind, CHANNEL.VOICE, source)
      }, TIMING.VOICE_PROCESS_MS)
    }, TIMING.VOICE_LISTEN_MS)
  }, [hasSchedule, later, markActivity, micState, online, student, track, voiceUnclear])

  const simulateUnclear = useCallback(() => {
    markActivity()
    setAnswer(null)
    setTranscript('')
    setMicState('listening')
    later(() => {
      setMicState('idle')
      setAnswer(UNCLEAR_ANSWER)
    }, TIMING.VOICE_LISTEN_MS)
  }, [later, markActivity])

  // ------------------------------------------------------------
  // แผงตัวควบคุมทดสอบ
  // ------------------------------------------------------------
  const sim = useMemo(
    () => ({
      presence: () => {
        detectPresence()
      },
      sleep: () => {
        clearTimers()
        setScreen('sleep')
      },
      recognized: () => {
        setFaceSim('recognized')
        setCameraOk(true)
        startScan()
      },
      unrecognized: () => {
        setFaceSim('unknown')
        setCameraOk(true)
        startScan()
      },
      multiFace: () => {
        setFaceSim('multi')
        setCameraOk(true)
        startScan()
      },
      noFace: () => {
        setFaceSim('notfound')
        setCameraOk(true)
        startScan()
      },
      cameraDown: () => {
        setCameraOk(false)
        startScan()
      },
      setOnline: (v) => setOnline(v),
      listening: () => {
        setVoiceUnclear(false)
        if (!PRIVATE_SCREENS.has(screen)) {
          setAnonymous(true)
          setScreen('assistant')
        } else if (screen !== 'assistant') {
          setScreen('assistant')
        }
        setTimeout(() => startListening(), 60)
      },
      unclear: () => {
        if (!PRIVATE_SCREENS.has(screen)) {
          setAnonymous(true)
          setScreen('assistant')
        } else if (screen !== 'assistant') {
          setScreen('assistant')
        }
        setTimeout(() => simulateUnclear(), 60)
      },
      setHasSchedule: (v) => setHasSchedule(v),
      setVoiceUnclear,
      setActiveStudentIdx,
      reset: () => {
        setFaceSim('recognized')
        setCameraOk(true)
        setOnline(true)
        setHasSchedule(true)
        setVoiceUnclear(false)
        setDeletedFaces(new Set())
        endSession()
      },
    }),
    [clearTimers, detectPresence, endSession, screen, simulateUnclear, startListening, startScan]
  )

  // ------------------------------------------------------------
  // ค่าที่คำนวณได้
  // ------------------------------------------------------------
  const activeStudent = STUDENTS[activeStudentIdx]
  const faceEnrolled = student ? !deletedFaces.has(student.id) : false
  const isAuthenticated = Boolean(student)

  const value = useMemo(
    () => ({
      now,
      screen,
      student,
      isAuthenticated,
      anonymous,
      online,
      cameraOk,
      hasSchedule,
      faceSim,
      voiceUnclear,
      activeStudent,
      activeStudentIdx,
      faceEnrolled,
      unknownReason,
      candidate,
      micState,
      transcript,
      answer,
      answerPending,
      enrollProgress,
      devOpen,
      events,
      logoutCountdown,
      // actions
      setDevOpen,
      setUnknownReason,
      setCandidate,
      setAnswer,
      setTranscript,
      setEnrollProgress,
      setScreen,
      markActivity,
      detectPresence,
      goto,
      startScan,
      confirmCandidate,
      loginWithStudentId,
      startAnonymous,
      startEnrollCapture,
      finishEnroll,
      deleteFaceData,
      askQuestion,
      startListening,
      endSession,
      track,
      sim,
    }),
    [
      now,
      screen,
      student,
      isAuthenticated,
      anonymous,
      online,
      cameraOk,
      hasSchedule,
      faceSim,
      voiceUnclear,
      activeStudent,
      activeStudentIdx,
      faceEnrolled,
      unknownReason,
      candidate,
      micState,
      transcript,
      answer,
      answerPending,
      enrollProgress,
      devOpen,
      events,
      logoutCountdown,
      markActivity,
      detectPresence,
      goto,
      startScan,
      confirmCandidate,
      loginWithStudentId,
      startAnonymous,
      startEnrollCapture,
      finishEnroll,
      deleteFaceData,
      askQuestion,
      startListening,
      endSession,
      track,
      sim,
    ]
  )

  return <KioskContext.Provider value={value}>{children}</KioskContext.Provider>
}
