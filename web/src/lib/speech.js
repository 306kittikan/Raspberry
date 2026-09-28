// ============================================================
// อ่านคำตอบออกเสียง
//
// ลองสองทางตามลำดับ
//   1. เสียงไทยที่ติดมากับเบราว์เซอร์  พูดทันที ไม่กินซีพียูของตู้
//   2. เสียงจากเซิร์ฟเวอร์ (Piper)      ใช้เมื่อเบราว์เซอร์ไม่มีเสียงไทย
//
// ต้องมีทั้งสองทางเพราะเครื่องพัฒนาเป็นวินโดวส์ซึ่งมีเสียงไทยให้อยู่แล้ว
// แต่ Chromium บนราสเบอร์รีพายไม่มี ถ้าพึ่งทางเดียวจะใช้ได้แค่เครื่องเดียว
//
// ไม่เก็บไฟล์เสียงไว้ในเบราว์เซอร์ เพราะนั่นคือร่องรอยของคำถามที่ผู้ใช้ถาม
// ============================================================

const BASE = import.meta.env.VITE_API_BASE ?? ''

let currentAudio = null
let serverReady = null // null = ยังไม่ได้ถาม

// ------------------------------------------------------------
// เสียงของเบราว์เซอร์
// ------------------------------------------------------------

// รายชื่อเสียงมาแบบไม่พร้อมกันในบางเบราว์เซอร์ ต้องรอเหตุการณ์
function voices() {
  if (typeof speechSynthesis === 'undefined') return []
  return speechSynthesis.getVoices() || []
}

function thaiVoice() {
  return voices().find((v) => (v.lang || '').toLowerCase().startsWith('th')) || null
}

export function browserThaiVoiceName() {
  return thaiVoice()?.name ?? null
}

function speakInBrowser(text) {
  const voice = thaiVoice()
  if (!voice) return false
  speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  u.voice = voice
  u.lang = voice.lang
  // ช้ากว่าปกติเล็กน้อย เพราะคำตอบมีรหัสวิชาและเลขห้องที่ต้องจดตาม
  u.rate = 0.95
  speechSynthesis.speak(u)
  return true
}

// ------------------------------------------------------------
// เสียงจากเซิร์ฟเวอร์
// ------------------------------------------------------------

async function speakFromServer(text) {
  const res = await fetch(BASE + '/api/tts/speak', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(`อ่านออกเสียงไม่สำเร็จ (HTTP ${res.status})`)

  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  currentAudio = audio
  // คืนหน่วยความจำทันทีที่เล่นจบ ตู้เปิดค้างทั้งวันจึงสะสมไม่ได้
  const release = () => URL.revokeObjectURL(url)
  audio.addEventListener('ended', release, { once: true })
  audio.addEventListener('error', release, { once: true })
  await audio.play()
}

export async function serverAvailable() {
  if (serverReady !== null) return serverReady
  try {
    const res = await fetch(BASE + '/api/tts/status')
    const data = await res.json()
    serverReady = Boolean(data?.ready)
  } catch {
    serverReady = false
  }
  return serverReady
}

// ------------------------------------------------------------

export function stop() {
  if (typeof speechSynthesis !== 'undefined') speechSynthesis.cancel()
  if (currentAudio) {
    currentAudio.pause()
    currentAudio = null
  }
}

export function supported() {
  return Boolean(thaiVoice()) || serverReady !== false
}

/** อ่านข้อความออกเสียง คืน true เมื่อได้พูดจริง */
export async function speak(text) {
  const clean = (text || '').trim()
  if (!clean) return false
  stop()

  if (speakInBrowser(clean)) return true
  if (!(await serverAvailable())) return false

  try {
    await speakFromServer(clean)
    return true
  } catch {
    return false
  }
}

// บางเบราว์เซอร์ส่งรายชื่อเสียงมาทีหลัง ขอให้ประเมินใหม่เมื่อรายชื่อมาถึง
export function onVoicesChanged(fn) {
  if (typeof speechSynthesis === 'undefined') return () => {}
  speechSynthesis.addEventListener('voiceschanged', fn)
  return () => speechSynthesis.removeEventListener('voiceschanged', fn)
}
