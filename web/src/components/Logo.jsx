import React, { useState } from 'react'
import { IconLogo } from './Icons'

/**
 * ตราสัญลักษณ์มหาวิทยาลัยแม่โจ้ (พระพิรุณทรงนาค)
 *
 * เป็นไฟล์ SVG จึงคมทุกขนาด ตั้งแต่ 56px บนแถบบน ไปจนถึง 180px บนจอพักลึก
 * สำคัญกับจอตู้ 1080×1920 ซึ่งใหญ่กว่าจอคอมพิวเตอร์ทั่วไปเกือบเท่าตัว
 *
 * ถ้าไฟล์หาย จะกลับไปใช้ไอคอนเวกเตอร์สำรองโดยอัตโนมัติ
 * เพื่อให้ตู้ยังเปิดใช้งานได้ตามปกติ ไม่ใช่ขึ้นเป็นรูปภาพเสียกลางจอ
 *
 * วิธีเปลี่ยน: แทนที่ไฟล์ web/public/logo-mju.svg
 */

const LOGO_SRC = '/logo-mju.svg'

export default function Logo({ className = '', tone = 'brand' }) {
  const [missing, setMissing] = useState(false)

  if (missing) {
    return <IconLogo className={className} />
  }

  const img = (
    <img
      src={LOGO_SRC}
      alt="ตราสัญลักษณ์มหาวิทยาลัยแม่โจ้"
      onError={() => setMissing(true)}
      // ตราสัญลักษณ์มีหลายสีในตัว จึงต้องไม่ถูกย้อมทับด้วยสีข้อความ
      className={`h-full w-full object-contain ${tone === 'dark' ? '' : className}`}
    />
  )

  if (tone !== 'dark') return img

  // บนพื้นเข้มต้องมีวงกลมขาวรองไว้ ไม่งั้นตัวอักษรเขียวบนตราจะจมหายไปกับพื้น
  //
  // ระยะขอบอยู่ที่กล่องครอบ ไม่ใช่ที่ตัว <img> โดยตรง
  // เพราะ padding แบบเปอร์เซ็นต์คิดจากความกว้างของกล่องแม่ ไม่ใช่ของตัวเอง
  // ถ้าใส่ไว้ที่ img กล่องแม่ที่กว้าง 1080px จะให้ระยะขอบใหญ่จนภาพหายไปทั้งใบ
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-full bg-white/90 p-[5px] ${className}`}
    >
      {img}
    </span>
  )
}
