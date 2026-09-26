import React from 'react'
import { useKiosk } from '../state/KioskProvider'
import { IconWifiOff } from './Icons'

/**
 * แถบแจ้งเตือนออฟไลน์ขนาดเล็ก
 * ปิดเฉพาะฟังก์ชัน AI ส่วนตารางเรียน/ข้อมูลจากฐานข้อมูลยังใช้ได้ตามปกติ
 */
export default function OfflineBanner() {
  const { online } = useKiosk()
  if (online) return null

  return (
    <div className="flex items-center gap-4 border-b-2 border-alert-100 bg-alert-50 px-12 py-4">
      <IconWifiOff className="h-8 w-8 shrink-0 text-alert-700" />
      <p className="text-label leading-snug text-alert-900">
        <span className="font-semibold">ไม่มีการเชื่อมต่ออินเทอร์เน็ต</span> — ผู้ช่วย AI ใช้งานไม่ได้ชั่วคราว
        ตารางเรียนและกำหนดสอบยังใช้งานได้ตามปกติ
      </p>
    </div>
  )
}
