import React, { useEffect, useState } from 'react'

export const STAGE_W = 1080
export const STAGE_H = 1920

/**
 * เวทีขนาดคงที่ 1080×1920 (จอสัมผัสแนวตั้งของตู้)
 * บนตู้จริงจะได้อัตราส่วน 1:1 พอดี ส่วนบนเครื่องพัฒนาจะย่อให้พอดีหน้าจอ
 * เพื่อให้ค่าพิกเซลทุกค่าในโค้ด (ตัวอักษร 24px, เป้าแตะ 72px) ตรงตามข้อกำหนดเสมอ
 */
export default function Stage({ children }) {
  const [scale, setScale] = useState(1)

  useEffect(() => {
    const fit = () => {
      const s = Math.min(window.innerWidth / STAGE_W, window.innerHeight / STAGE_H)
      setScale(s)
    }
    fit()
    window.addEventListener('resize', fit)
    window.addEventListener('orientationchange', fit)
    return () => {
      window.removeEventListener('resize', fit)
      window.removeEventListener('orientationchange', fit)
    }
  }, [])

  return (
    <div className="fixed inset-0 flex items-center justify-center overflow-hidden bg-black">
      <div
        style={{
          width: STAGE_W,
          height: STAGE_H,
          transform: `scale(${scale})`,
          transformOrigin: 'center center',
        }}
        className="relative shrink-0 overflow-hidden bg-brand-50"
      >
        {children}
      </div>
    </div>
  )
}
