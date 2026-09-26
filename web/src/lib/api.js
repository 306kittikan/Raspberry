// ============================================================
// ตัวเรียก API ของตู้
//
// หน้าเว็บไม่เก็บข้อมูลส่วนบุคคลไว้เองเลย ทุกอย่างขอจากเซิร์ฟเวอร์
// และผูกกับโทเค็นเซสชันที่เซิร์ฟเวอร์ออกให้ ไม่ใช่รหัสนักศึกษาที่หน้าเว็บถืออยู่
//
// โทเค็นเก็บในตัวแปรในหน่วยความจำเท่านั้น ไม่ใช้ localStorage
// รีเฟรชหน้าจอแล้วเซสชันต้องหาย เพื่อไม่ให้ข้อมูลค้างอยู่บนตู้
// ============================================================

const BASE = import.meta.env.VITE_API_BASE ?? ''

let sessionToken = null

export function getSessionToken() {
  return sessionToken
}

export function setSessionToken(token) {
  sessionToken = token || null
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `คำขอล้มเหลว (HTTP ${status})`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request(method, path, body) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (sessionToken) headers['X-Kiosk-Session'] = sessionToken

  const res = await fetch(BASE + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  const text = await res.text()
  const data = text ? JSON.parse(text) : null

  if (!res.ok) {
    throw new ApiError(res.status, data?.detail)
  }
  return data
}

const get = (path) => request('GET', path)
const post = (path, body = {}) => request('POST', path, body)
const del = (path) => request('DELETE', path)

// ------------------------------------------------------------
// ข้อมูลทั่วไป (ไม่ต้องยืนยันตัวตน)
// ------------------------------------------------------------
export const bootstrap = () => get('/api/bootstrap')
export const health = () => get('/api/health')

// ------------------------------------------------------------
// เซสชัน
// ------------------------------------------------------------
export async function confirmFace(candidateToken) {
  const data = await post('/api/session/face-confirm', { candidateToken })
  setSessionToken(data.token)
  return data
}

export async function loginWithStudentId(studentId) {
  const data = await post('/api/session/student-id', { studentId })
  setSessionToken(data.token)
  return data
}

export async function startAnonymous() {
  const data = await post('/api/session/anonymous')
  setSessionToken(data.token)
  return data
}

export function keepAlive() {
  if (!sessionToken) return Promise.resolve({ alive: false })
  return post('/api/session/touch').catch(() => ({ alive: false }))
}

export async function logout() {
  if (!sessionToken) return
  try {
    await del('/api/session')
  } finally {
    setSessionToken(null)
  }
}

// ------------------------------------------------------------
// ข้อมูลส่วนบุคคล
// ------------------------------------------------------------
export const getSchedule = () => get('/api/me/schedule')
export const getExams = () => get('/api/me/exams')
export const getFaceStatus = () => get('/api/me/face')
export const deleteFaceData = () => del('/api/me/face')

// ------------------------------------------------------------
// ผู้ช่วยตอบคำถาม
// ------------------------------------------------------------
export async function ask(questionId, { channel = 'แตะ', online = true } = {}) {
  const data = await post('/api/assistant/ask', { questionId, channel, online })
  return data.answer
}

/** ถามด้วยข้อความที่ผู้ใช้พิมพ์เอง — เซิร์ฟเวอร์ตีความแล้วเลือกทางตอบให้ */
export async function askText(text, { online = true } = {}) {
  const data = await post('/api/assistant/ask', { text, channel: 'พิมพ์', online })
  return data.answer
}

export const unclearAnswer = () => get('/api/assistant/unclear').then((d) => d.answer)

// ------------------------------------------------------------
// กล้องและการรู้จำใบหน้า
// ------------------------------------------------------------
/** ที่อยู่ภาพสดจากกล้อง ใช้ใส่ใน <img src> ได้โดยตรง */
export const cameraStreamUrl = () => `${BASE}/api/face/stream?t=${Date.now()}`

export const faceStatus = () => get('/api/face/status')
export const startScan = () => post('/api/face/scan/start')
export const stopScan = () => post('/api/face/scan/stop')
/** ขั้นที่ 1: ยินยอมแล้วถ่ายใบหน้าทันที ยังไม่ต้องรู้ว่าเป็นใคร */
export const beginEnroll = (policyVersion) =>
  post('/api/face/enroll/begin', { agreed: true, policyVersion })

/** ขั้นที่ 2: บอกว่าใบหน้าที่ถ่ายไว้เป็นของรหัสนักศึกษาใด แล้วรับเซสชันกลับมา */
export async function completeEnroll(pendingToken, studentId) {
  const data = await post('/api/face/enroll/complete', { pendingToken, studentId })
  setSessionToken(data.token)
  return data
}

export const cancelEnroll = (pendingToken) =>
  post('/api/face/enroll/cancel', pendingToken ? { pendingToken } : {})

// ------------------------------------------------------------
// ช่องทางเสียง
// ------------------------------------------------------------
export const voiceStatus = () => get('/api/voice/status')

// ------------------------------------------------------------
// โหมดจำลอง (เปิดเฉพาะตอนพัฒนา)
// ------------------------------------------------------------
export const sim = {
  students: () => get('/api/sim/students'),
  faceRecognized: (studentId) =>
    post('/api/sim/face/recognized', studentId ? { studentId } : {}),
  faceProblem: (result) => post(`/api/sim/face/${result}`),
  presence: (state) => post(`/api/sim/presence/${state}`),
  voice: (state, body = {}) => post(`/api/sim/voice/${state}`, body),
}

// ------------------------------------------------------------
// ช่องรับเหตุการณ์จากกล้อง/ไมโครโฟน/เซ็นเซอร์
// ------------------------------------------------------------
export function connectEvents(onEvent) {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const url = BASE
    ? BASE.replace(/^http/, 'ws') + '/ws/kiosk'
    : `${proto}://${window.location.host}/ws/kiosk`

  let socket = null
  let retry = null
  let closed = false

  const open = () => {
    if (closed) return
    socket = new WebSocket(url)
    socket.onmessage = (ev) => {
      try {
        onEvent(JSON.parse(ev.data))
      } catch {
        // ข้อความที่อ่านไม่ออกให้ข้ามไป ตู้ต้องไม่ล้มเพราะเหตุการณ์เดียว
      }
    }
    // ตู้ต้องกลับมาเองได้เสมอ ถ้าเซิร์ฟเวอร์รีสตาร์ตระหว่างวัน
    socket.onclose = () => {
      if (!closed) retry = setTimeout(open, 2000)
    }
    socket.onerror = () => socket?.close()
  }

  open()

  return () => {
    closed = true
    clearTimeout(retry)
    socket?.close()
  }
}
