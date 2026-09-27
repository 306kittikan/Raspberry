// ============================================================
// อัดเสียงจากไมโครโฟนแล้วส่งให้เซิร์ฟเวอร์ถอดความ
//
// ใช้ MediaRecorder ซึ่งได้เสียงบีบอัด (webm/opus) มาเลย
// จึงไม่ต้องเขียน AudioWorklet แปลงสัญญาณเอง และข้อมูลที่ส่งเล็กกว่ามาก
// ฝั่งเซิร์ฟเวอร์ถอดรหัสด้วย PyAV ที่ติดมากับ faster-whisper อยู่แล้ว
//
// เสียงไม่ถูกบันทึกลงดิสก์ทั้งฝั่งเบราว์เซอร์และฝั่งเซิร์ฟเวอร์
// ============================================================

const BASE = import.meta.env.VITE_API_BASE ?? ''

function socketUrl() {
  if (BASE) return BASE.replace(/^http/, 'ws') + '/ws/voice'
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws/voice`
}

/** เบราว์เซอร์รองรับการอัดเสียงหรือไม่ (ต้องเป็น localhost หรือ https) */
export function isSupported() {
  return Boolean(
    navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== 'undefined'
  )
}

function pickMimeType() {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']
  return candidates.find((t) => MediaRecorder.isTypeSupported(t)) ?? ''
}

/**
 * เปิดช่องทางเสียงค้างไว้หนึ่งช่อง แล้วใช้ซ้ำทุกครั้งที่ผู้ใช้กดพูด
 * onMessage รับสถานะจากเซิร์ฟเวอร์: listening / processing / transcript / answer / unclear / error
 */
export function createVoiceChannel(onMessage) {
  let socket = null
  let stream = null
  let recorder = null
  let closed = false
  let retry = null

  const connect = () => {
    if (closed) return
    socket = new WebSocket(socketUrl())
    socket.binaryType = 'arraybuffer'
    socket.onmessage = (ev) => {
      try {
        onMessage(JSON.parse(ev.data))
      } catch {
        // ข้อความที่อ่านไม่ออกให้ข้ามไป ตู้ต้องไม่ล้มเพราะข้อความเดียว
      }
    }
    socket.onclose = () => {
      if (!closed) retry = setTimeout(connect, 2000)
    }
    socket.onerror = () => socket?.close()
  }

  connect()

  const ready = () => socket && socket.readyState === WebSocket.OPEN

  return {
    get recording() {
      return recorder?.state === 'recording'
    },

    /** ขอสิทธิ์ใช้ไมโครโฟนล่วงหน้า เพื่อไม่ให้ผู้ใช้เจอกล่องขออนุญาตตอนกดพูด */
    async prime() {
      if (stream) return true
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            // เสียงพูดไม่ต้องใช้สองช่อง ช่องเดียวเล็กกว่าและถอดความได้เท่ากัน
            channelCount: 1,
            // ขอ 48 kHz ไว้ก่อน แล้วให้ฝั่งเซิร์ฟเวอร์ลดเหลือ 16 kHz เอง
            // การลดจากของดีทำได้สะอาดกว่าการขอต่ำตั้งแต่ต้นแล้วได้เสียงที่บางไปแล้ว
            sampleRate: 48000,

            // ตัดเสียงรบกวนของเบราว์เซอร์ออกแบบเปิด/ปิดเท่านั้น ปรับความแรงไม่ได้
            // เมื่อเปิด มันจะกดย่านความถี่ที่มันคิดว่าเป็นเสียงรบกวนทิ้ง
            // ซึ่งกินเสียงพยัญชนะเบา ๆ ของภาษาไทยอย่าง ส ฉ ถ ไปด้วย
            // ตัวถอดความอาศัยเสียงเหล่านี้แยกคำ จึงปิดไว้แล้วให้ตัวถอดความจัดการเอง
            noiseSuppression: false,

            // ปรับระดับเสียงอัตโนมัติ ทำให้ความดังไม่สม่ำเสมอระหว่างประโยค
            // และดึงเสียงพื้นหลังขึ้นมาในจังหวะที่คนหยุดพูด
            autoGainControl: false,

            // เปิดไว้เพราะตู้ใช้ลำโพง ไม่ใช่หูฟัง
            // ถ้าไม่ตัด เสียงที่ตู้พูดตอบจะวนกลับเข้าไมค์แล้วถูกถอดความซ้ำ
            echoCancellation: true,
          },
        })
        return true
      } catch {
        return false
      }
    },

    async start() {
      if (!ready()) return false
      if (!(await this.prime())) return false
      if (recorder?.state === 'recording') return true

      // ค่าปริยายของเบราว์เซอร์สำหรับเสียงพูดอยู่ราว 32 kbps ซึ่งบีบอัดแรงเกินไป
      // รายละเอียดที่หายไปคือสิ่งที่ตัวถอดความใช้แยกคำที่เสียงใกล้กัน
      recorder = new MediaRecorder(stream, {
        mimeType: pickMimeType(),
        audioBitsPerSecond: 128000,
      })
      recorder.ondataavailable = (ev) => {
        if (ev.data.size > 0 && ready()) {
          ev.data.arrayBuffer().then((buf) => ready() && socket.send(buf))
        }
      }
      socket.send(JSON.stringify({ type: 'start' }))
      // ส่งเป็นก้อนย่อยระหว่างพูด เพื่อไม่ให้ต้องรอส่งก้อนใหญ่ทีเดียวตอนจบ
      recorder.start(250)
      return true
    },

    /** หยุดพูด แล้วบอกเซิร์ฟเวอร์ให้เริ่มถอดความ */
    stop(context = {}) {
      if (!recorder || recorder.state !== 'recording') return
      recorder.onstop = () => {
        if (ready()) socket.send(JSON.stringify({ type: 'stop', ...context }))
      }
      recorder.stop()
      recorder = null
    },

    close() {
      closed = true
      clearTimeout(retry)
      try {
        recorder?.stop()
      } catch {
        // กำลังปิดอยู่แล้ว ไม่ต้องสนใจ
      }
      stream?.getTracks().forEach((t) => t.stop())
      stream = null
      socket?.close()
    },
  }
}
