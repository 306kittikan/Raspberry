import React, { useMemo } from 'react'
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
  const streamUrl = useMemo(() => api.cameraStreamUrl(), [])

  if (!cameraOk) {
    return (
      <div
        className={`flex items-center justify-center bg-[#0C1A13] ${rounded} ${className}`}
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
      <div className={`flex items-center justify-center bg-[#0C1A13] ${rounded} ${className}`}>
        <div className="text-center">
          <IconFace className="mx-auto h-20 w-20 text-brand-500/50" />
          <p className="mt-4 text-label text-white/50">กำลังเปิดกล้อง…</p>
        </div>
      </div>
    )
  }

  return (
    <img
      src={streamUrl}
      alt=""
      className={`scale-x-[-1] bg-[#0C1A13] object-cover ${rounded} ${className}`}
    />
  )
}
