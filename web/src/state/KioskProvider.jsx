import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import * as api from '../lib/api'
import { CHANNEL, SOURCE, logEvent } from '../lib/logger'

// ------------------------------------------------------------
// ค่าคงที่ของพฤติกรรมตู้
// ------------------------------------------------------------
export const TIMING = {
  SLEEP_AFTER_MS: 120_000, // ไม่มีคนเกิน 2 นาที → จอพักลึก
  IDLE_LOGOUT_MS: 30_000, // ไม่มีการใช้งาน 30 วินาที → เตือน
  LOGOUT_COUNTDOWN_S: 10, // นับถอยหลัง 10 วินาที ก่อนออกจากระบบ
  FACE_DETECT_MS: 2_600, // เวลาที่ปล่อยให้กล้องตรวจจับก่อนสรุปผล
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

const EMPTY_SCHEDULE = {
  hasSchedule: false,
  today: [],
  week: { 1: [], 2: [], 3: [], 4: [], 5: [] },
  nextClass: null,
  todayLabel: '',
}

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

  // ---- ข้อมูลตั้งต้นจากเซิร์ฟเวอร์ ----
  const [boot, setBoot] = useState(null)
  const [bootError, setBootError] = useState(null)
  const [simStudents, setSimStudents] = useState([])

  // ---- สถานะหลัก ----
  const [screen, setScreen] = useState('idle')
  const [student, setStudent] = useState(null)
  const [schedule, setSchedule] = useState(EMPTY_SCHEDULE)
  const [exams, setExams] = useState([])
  const [anonymous, setAnonymous] = useState(false)

  // ---- สถานะอุปกรณ์/เครือข่าย ----
  const [online, setOnline] = useState(() => navigator.onLine)
  const [cameraOk, setCameraOk] = useState(true)
  const [faceSim, setFaceSim] = useState('recognized') // recognized | unknown | multi | notfound
  const [voiceUnclear, setVoiceUnclear] = useState(false)
  const [forceNoSchedule, setForceNoSchedule] = useState(false)
  const [activeStudentIdx, setActiveStudentIdx] = useState(0)

  // ---- สถานะย่อยของแต่ละหน้า ----
  const [unknownReason, setUnknownReason] = useState('unrecognized')
  const [candidate, setCandidate] = useState(null) // ผู้ที่ระบบคิดว่าใช่ (ยังไม่ยืนยัน)
  const [faceEnrolled, setFaceEnrolled] = useState(false)
  const [faceEnrolledAtLabel, setFaceEnrolledAtLabel] = useState(null)
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
  // โหลดข้อมูลตั้งต้นครั้งเดียวตอนเปิดตู้
  // ------------------------------------------------------------
  useEffect(() => {
    let alive = true
    api
      .bootstrap()
      .then((data) => {
        if (alive) setBoot(data)
      })
      .catch((err) => {
        if (alive) setBootError(err.message)
      })
    // รายชื่อสำหรับแผงทดสอบ — เซิร์ฟเวอร์เปิดให้เฉพาะโหมดจำลอง
    api.sim
      .students()
      .then((d) => alive && setSimStudents(d.students))
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [])

  // ------------------------------------------------------------
  // สถานะเครือข่าย
  // ------------------------------------------------------------
  useEffect(() => {
    const up = () => setOnline(true)
    const down = () => setOnline(false)
    window.addEventListener('online', up)
    window.addEventListener('offline', down)
    return () => {
      window.removeEventListener('online', up)
      window.removeEventListener('offline', down)
    }
  }, [])

  // ------------------------------------------------------------
  // บันทึกเหตุการณ์บนหน้าจอ (สถิติตัวจริงเซิร์ฟเวอร์เป็นผู้บันทึก)
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
    api.keepAlive()
  }, [])

  const detectPresence = useCallback(() => {
    setLastPresenceAt(Date.now())
    setScreen((s) => (s === 'sleep' ? 'idle' : s))
  }, [])

  // ------------------------------------------------------------
  // จบการใช้งาน: ล้างข้อมูลบนจอและบนเซิร์ฟเวอร์ทั้งหมด
  // ------------------------------------------------------------
  const endSession = useCallback(
    (reason = 'manual') => {
      clearTimers()
      api.logout()
      setStudent(null)
      setSchedule(EMPTY_SCHEDULE)
      setExams([])
      setCandidate(null)
      setAnonymous(false)
      setFaceEnrolled(false)
      setFaceEnrolledAtLabel(null)
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
  // โหลดข้อมูลส่วนบุคคลหลังยืนยันตัวตนสำเร็จ
  // ------------------------------------------------------------
  const loadPersonalData = useCallback(async ({ withFace }) => {
    const [sched, ex] = await Promise.all([api.getSchedule(), api.getExams()])
    setSchedule(sched)
    setExams(ex.exams)
    if (withFace) {
      try {
        const face = await api.getFaceStatus()
        setFaceEnrolled(face.enrolled)
        setFaceEnrolledAtLabel(face.enrolledAtLabel)
      } catch {
        setFaceEnrolled(false)
        setFaceEnrolledAtLabel(null)
      }
    }
  }, [])

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

  /** เริ่มสแกนใบหน้า — ผลลัพธ์มาจากเซิร์ฟเวอร์ผ่าน WebSocket */
  const startScan = useCallback(() => {
    clearTimers()
    markActivity()
    setAnswer(null)
    setTranscript('')
    setCandidate(null)
    setScreen('scan')

    // โหมดจำลอง: ขอให้เซิร์ฟเวอร์ปล่อยเหตุการณ์ตามผลที่แผงทดสอบเลือกไว้
    // เมื่อมีกล้องจริง ส่วนนี้จะถูกแทนที่ด้วยบริการกล้องที่ผลักเหตุการณ์เข้ามาเอง
    if (!cameraOk) {
      later(() => api.sim.faceProblem('camera_error').catch(() => {}), 600)
      return
    }
    const delay = faceSim === 'notfound' ? TIMING.FACE_TIMEOUT_MS : TIMING.FACE_DETECT_MS
    later(() => {
      const target = simStudents[activeStudentIdx]
      const call =
        faceSim === 'recognized'
          ? api.sim.faceRecognized(target?.studentId)
          : api.sim.faceProblem(faceSim)
      call.catch(() => {})
    }, delay)
  }, [activeStudentIdx, cameraOk, clearTimers, faceSim, later, markActivity, simStudents])

  // ------------------------------------------------------------
  // เหตุการณ์จากกล้อง/ไมโครโฟน/เซ็นเซอร์
  // ------------------------------------------------------------
  const handleEvent = useCallback(
    (ev) => {
      if (ev.kind === 'presence') {
        if (ev.state === 'detected') detectPresence()
        else setLastPresenceAt(Date.now() - TIMING.SLEEP_AFTER_MS - 1000)
        return
      }

      if (ev.kind === 'face') {
        setFaceSim(ev.result === 'camera_error' ? 'notfound' : ev.result)
        if (ev.result === 'recognized') {
          setCameraOk(true)
          setCandidate({ token: ev.candidateToken, name: ev.name, score: ev.score })
          setScreen('confirm')
        } else if (ev.result === 'unknown') {
          setUnknownReason('unrecognized')
          setScreen('unknown')
        } else if (ev.result === 'notfound') {
          setUnknownReason('timeout')
          setScreen('unknown')
        } else if (ev.result === 'camera_error') {
          setCameraOk(false)
          setUnknownReason('camera')
          setScreen('keypad')
        }
        // 'multi' : ค้างอยู่หน้าสแกนพร้อมคำเตือน ไม่แสดงข้อมูลใด ๆ
        return
      }

      if (ev.kind === 'voice') {
        if (ev.state === 'listening') setMicState('listening')
        else if (ev.state === 'processing') setMicState('processing')
        else if (ev.state === 'transcript' && ev.transcript) setTranscript(ev.transcript)
        else if (ev.state === 'unclear') setMicState('idle')
      }
    },
    [detectPresence]
  )

  const handleEventRef = useRef(handleEvent)
  handleEventRef.current = handleEvent

  useEffect(() => api.connectEvents((ev) => handleEventRef.current(ev)), [])

  // ------------------------------------------------------------
  // ยืนยันตัวตน
  // ------------------------------------------------------------
  const confirmCandidate = useCallback(
    async (yes) => {
      markActivity()
      if (!yes || !candidate) {
        setCandidate(null)
        setUnknownReason('unrecognized')
        setScreen('unknown')
        return
      }
      try {
        const sess = await api.confirmFace(candidate.token)
        setStudent(sess.student)
        setAnonymous(false)
        await loadPersonalData({ withFace: true })
        setScreen('home')
        track('เข้าสู่ระบบด้วยใบหน้า', CHANNEL.TOUCH, SOURCE.DB)
      } catch {
        // ผลการรู้จำหมดอายุ หรือเซิร์ฟเวอร์ปฏิเสธ → ให้ผู้ใช้เลือกวิธีอื่น
        setCandidate(null)
        setUnknownReason('unrecognized')
        setScreen('unknown')
      }
    },
    [candidate, loadPersonalData, markActivity, track]
  )

  const loginWithStudentId = useCallback(
    async (id) => {
      markActivity()
      try {
        const sess = await api.loginWithStudentId(id)
        setStudent(sess.student)
        setAnonymous(false)
        await loadPersonalData({ withFace: false })
        setScreen('home')
        track('เข้าสู่ระบบด้วยรหัสนักศึกษา', CHANNEL.TOUCH, SOURCE.DB)
        return true
      } catch {
        return false
      }
    },
    [loadPersonalData, markActivity, track]
  )

  const startAnonymous = useCallback(async () => {
    markActivity()
    setStudent(null)
    setSchedule(EMPTY_SCHEDULE)
    setExams([])
    setAnswer(null)
    setTranscript('')
    setAnonymous(true)
    setScreen('assistant')
    try {
      await api.startAnonymous()
    } catch {
      // ถ้าเปิดเซสชันไม่ได้ ยังใช้งานต่อได้ เพียงแต่ตอบได้เฉพาะคำถามทั่วไป
    }
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

  const finishEnroll = useCallback(async () => {
    markActivity()
    // เมื่อมีกล้องจริง ขั้นนี้จะส่งเวกเตอร์ใบหน้าขึ้นเซิร์ฟเวอร์พร้อมรหัสความยินยอม
    // ตอนนี้ใช้การเข้าสู่ระบบด้วยรหัสนักศึกษาของผู้ที่เลือกไว้ในแผงทดสอบแทน
    const target = simStudents[activeStudentIdx]
    if (target && (await loginWithStudentId(target.studentId))) {
      setFaceEnrolled(true)
      track('ลงทะเบียนใบหน้าสำเร็จ', CHANNEL.TOUCH, SOURCE.DB)
    }
  }, [activeStudentIdx, loginWithStudentId, markActivity, simStudents, track])

  const deleteFaceData = useCallback(async () => {
    markActivity()
    try {
      await api.deleteFaceData()
      setFaceEnrolled(false)
      setFaceEnrolledAtLabel(null)
      track('ลบข้อมูลใบหน้า', CHANNEL.TOUCH, SOURCE.DB)
    } catch {
      setFaceEnrolled(false)
    }
  }, [markActivity, track])

  // ------------------------------------------------------------
  // ถาม–ตอบ
  // ------------------------------------------------------------
  const askQuestion = useCallback(
    async (questionId, channel = CHANNEL.TOUCH) => {
      markActivity()
      setAnswerPending(true)
      setAnswer(null)
      try {
        const result = await api.ask(questionId, { channel, online })
        setAnswer(result)
        const source =
          result.source === 'ai' ? SOURCE.AI : result.source === 'db' ? SOURCE.DB : SOURCE.AI
        track(result.kind || 'คำถาม', channel, source)
      } catch {
        setAnswer({
          source: 'none',
          title: 'ติดต่อระบบของตู้ไม่ได้',
          lines: ['กรุณาลองใหม่อีกครั้ง หรือติดต่อสำนักงานสาขาวิชาฯ'],
        })
      } finally {
        setAnswerPending(false)
      }
    },
    [markActivity, online, track]
  )

  /** เริ่มฟังเสียง — เมื่อมีไมโครโฟนจริง ขั้นนี้จะเป็นการเปิดสตรีมเสียงไปยังเซิร์ฟเวอร์ */
  const startListening = useCallback(() => {
    if (micState !== 'idle') return
    markActivity()
    setAnswer(null)
    setTranscript('')
    setMicState('listening')

    later(async () => {
      if (voiceUnclear) {
        setMicState('idle')
        setAnswer(await api.unclearAnswer().catch(() => null))
        return
      }
      const pool = (boot?.quickQuestions || []).filter((q) => !q.personal || student)
      if (pool.length === 0) {
        setMicState('idle')
        return
      }
      const pick = pool[Math.floor(Math.random() * pool.length)]
      setTranscript(pick.label)
      setMicState('processing')

      later(async () => {
        await askQuestion(pick.id, CHANNEL.VOICE)
        setMicState('idle')
      }, TIMING.VOICE_PROCESS_MS)
    }, TIMING.VOICE_LISTEN_MS)
  }, [askQuestion, boot, later, markActivity, micState, student, voiceUnclear])

  const simulateUnclear = useCallback(() => {
    markActivity()
    setAnswer(null)
    setTranscript('')
    setMicState('listening')
    later(async () => {
      setMicState('idle')
      setAnswer(await api.unclearAnswer().catch(() => null))
    }, TIMING.VOICE_LISTEN_MS)
  }, [later, markActivity])

  // ------------------------------------------------------------
  // แผงตัวควบคุมทดสอบ
  // ------------------------------------------------------------
  const sim = useMemo(
    () => ({
      presence: () => api.sim.presence('detected').catch(detectPresence),
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
      setHasSchedule: (v) => setForceNoSchedule(!v),
      setVoiceUnclear,
      setActiveStudentIdx,
      reset: () => {
        setFaceSim('recognized')
        setCameraOk(true)
        setOnline(navigator.onLine)
        setForceNoSchedule(false)
        setVoiceUnclear(false)
        endSession()
      },
    }),
    [clearTimers, detectPresence, endSession, screen, simulateUnclear, startListening, startScan]
  )

  // ------------------------------------------------------------
  // ค่าที่คำนวณได้
  // ------------------------------------------------------------
  const hasSchedule = schedule.hasSchedule && !forceNoSchedule
  const effectiveSchedule = forceNoSchedule ? EMPTY_SCHEDULE : schedule
  const effectiveExams = forceNoSchedule ? [] : exams
  const activeStudent = simStudents[activeStudentIdx] || null
  const isAuthenticated = Boolean(student)

  const value = useMemo(
    () => ({
      now,
      screen,
      // ข้อมูลตั้งต้นจากเซิร์ฟเวอร์
      boot,
      bootError,
      department: boot?.department ?? null,
      announcements: boot?.announcements ?? [],
      quickQuestions: boot?.quickQuestions ?? [],
      dataUpdatedLabel: boot?.term?.dataUpdatedLabel ?? null,
      hasSyntheticSchedule: boot?.hasSyntheticSchedule ?? false,
      termLabel: boot?.term?.label ?? null,
      // ผู้ใช้ปัจจุบัน
      student,
      isAuthenticated,
      anonymous,
      schedule: effectiveSchedule,
      exams: effectiveExams,
      hasSchedule,
      faceEnrolled,
      faceEnrolledAtLabel,
      // อุปกรณ์
      online,
      cameraOk,
      faceSim,
      voiceUnclear,
      simStudents,
      activeStudent,
      activeStudentIdx,
      // สถานะหน้าจอ
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
      now, screen, boot, bootError, student, isAuthenticated, anonymous,
      effectiveSchedule, effectiveExams, hasSchedule, faceEnrolled, faceEnrolledAtLabel,
      online, cameraOk, faceSim, voiceUnclear, simStudents, activeStudent,
      activeStudentIdx, unknownReason, candidate, micState, transcript,
      answer, answerPending, enrollProgress, devOpen, events, logoutCountdown,
      markActivity, detectPresence, goto, startScan, confirmCandidate,
      loginWithStudentId, startAnonymous, startEnrollCapture, finishEnroll,
      deleteFaceData, askQuestion, startListening, endSession, track, sim,
    ]
  )

  return <KioskContext.Provider value={value}>{children}</KioskContext.Provider>
}
