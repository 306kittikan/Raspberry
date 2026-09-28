import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useKiosk } from '../state/KioskProvider'
import * as api from '../lib/api'
import { IconCameraOff, IconFace } from './Icons'

/**
 * ภาพสดจากกล้องของตู้
 *
 * ที่อยู่สตรีมคำนวณครั้งเดียวต่อการ mount หนึ่งครั้ง
 * ถ้าเปลี่ยนทุกครั้งที่เรนเดอร์ เบราว์เซอร์จะเปิดการเชื่อมต่อใหม่เรื่อย ๆ จนภาพกระตุก
 *
 * กลับด้านซ้ายขวาเหมือนส่องกระจก เพราะผู้ใช้ขยับตัวตามภาพที่เห็น
 * ถ้าไม่กลับด้านจะรู้สึกว่าขยับผิดทางทุกครั้ง
 */
export default function CameraView({ className = '', rounded = 'rounded-[28px]' }) {
  const { cameraReady, cameraOk } = useKiosk()
  // เซิร์ฟเวอร์ตัดภาพสดทิ้งเองเมื่อครบอายุ เพื่อไม่ให้สายค้างสะสมจนตู้ตอบไม่ไหว
  // ฝั่งนี้จึงต้องขอสายใหม่เมื่อถูกตัด ไม่งั้นภาพจะดับไปเฉย ๆ แล้วไม่กลับมา
  const [attempt, setAttempt] = useState(0)
  const [url, setUrl] = useState(() => api.cameraStreamUrl())
  const timer = useRef(null)

  useEffect(() => {
    if (attempt > 0) setUrl(api.cameraStreamUrl())
  }, [attempt])

  useEffect(() => () => clearTimeout(timer.current), [])

  const retry = useCallback(() => {
    clearTimeout(timer.current)
    // หน่วงก่อนลองใหม่ ถ้าเซิร์ฟเวอร์ปฏิเสธเพราะมีสายเปิดอยู่มากเกินไป
    // การยิงซ้ำทันทีจะยิ่งทำให้แย่ลง
    timer.current = setTimeout(() => setAttempt((n) => n + 1), 1200)
  }, [])

  if (!cameraOk) {
    return (
      <div
        className={`flex items-center justify-center bg-[#0B1622] ${rounded} ${className}`}
      >
        <div className="text-center">
          <IconCameraOff className="mx-auto h-20 w-20 text-danger-100" />
          <p className="mt-4 text-label text-white/60">กล้องใช้งานไม่ได้</p>
        </div>
      </div>
    )
  }

  if (!cameraReady) {
    return (
      <div className={`flex items-center justify-center bg-[#0B1622] ${rounded} ${className}`}>
        <div className="text-center">
          <IconFace className="mx-auto h-20 w-20 text-brand-500/50" />
          <p className="mt-4 text-label text-white/50">กำลังเปิดกล้อง…</p>
        </div>
      </div>
    )
  }

  return (
    <img
      key={url}
      src={url}
      alt=""
      onError={retry}
      className={`scale-x-[-1] bg-[#0B1622] object-cover ${rounded} ${className}`}
    />
  )
}
