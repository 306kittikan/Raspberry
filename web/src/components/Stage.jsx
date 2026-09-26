import React, { createContext, useContext, useEffect, useState } from 'react'

export const STAGE_W = 1080
export const STAGE_H = 1920

/**
 * หน้าจอของตู้จริงเป็นแนวตั้ง 1080×1920 แต่ตอนพัฒนาบน Windows
 * จอเป็นแนวนอน ถ้าย่อทั้งเวทีให้พอดีความสูงจะเหลือเป็นแถบแคบ ๆ กลางจอดำ
 *
 * จึงแยกเป็นสองโหมด
 *   kiosk    จอแนวตั้ง (หรือจอที่สูงกว่ากว้าง) — ย่อเวทีให้พอดีเหมือนเดิม
 *   desktop  จอแนวนอน — วางแผงด้านข้างไว้ซ้าย แล้วให้เวทีอยู่ขวา
 *
 * ทั้งสองโหมดใช้หน้าจอชุดเดียวกัน ขนาดตัวอักษรและเป้าแตะจึงยังตรงตามข้อกำหนดเสมอ
 * โหมด desktop แค่เพิ่มพื้นที่ว่างด้านข้างมาใช้ประโยชน์ ไม่ได้แก้เนื้อหาข้างใน
 */

const LayoutContext = createContext({ mode: 'kiosk', scale: 1 })

export function useLayout() {
  return useContext(LayoutContext)
}

/** จอที่กว้างกว่าสูงพอสมควรถือเป็นจอคอมพิวเตอร์ ไม่ใช่จอตู้ */
const DESKTOP_RATIO = 1.15

/** แผงด้านข้างกว้างได้ไม่เกินกี่เท่าของหน้าจอตู้ */
const ASIDE_MAX_RATIO = 1.25

export default function Stage({ children, aside }) {
  const [box, setBox] = useState(() => ({ mode: 'kiosk', scale: 1, asideWidth: 0 }))

  useEffect(() => {
    const fit = () => {
      const w = window.innerWidth
      const h = window.innerHeight
      const desktop = w / h >= DESKTOP_RATIO && aside

      if (!desktop) {
        setBox({
          mode: 'kiosk',
          scale: Math.min(w / STAGE_W, h / STAGE_H),
          asideWidth: 0,
        })
        return
      }

      // โหมดจอคอมพิวเตอร์: เวทีสูงเต็มจอ ที่เหลือยกให้แผงด้านข้าง
      const scale = h / STAGE_H
      const stageWidth = STAGE_W * scale
      // จำกัดความกว้างแผงด้านข้างไม่ให้กลืนหน้าจอตู้
      // บนจอกว้างมาก ๆ ที่เหลือจะกลายเป็นขอบดำสองข้าง ซึ่งอ่านง่ายกว่าแผงยักษ์
      const asideWidth = Math.min(
        Math.max(0, w - stageWidth),
        stageWidth * ASIDE_MAX_RATIO
      )
      setBox({ mode: 'desktop', scale, asideWidth })
    }

    fit()
    window.addEventListener('resize', fit)
    window.addEventListener('orientationchange', fit)
    return () => {
      window.removeEventListener('resize', fit)
      window.removeEventListener('orientationchange', fit)
    }
  }, [aside])

  const stage = (
    <div
      style={{
        width: STAGE_W,
        height: STAGE_H,
        transform: `scale(${box.scale})`,
        transformOrigin: box.mode === 'desktop' ? 'top left' : 'center center',
      }}
      className="relative shrink-0 overflow-hidden bg-brand-50"
    >
      {children}
    </div>
  )

  if (box.mode === 'desktop') {
    return (
      <LayoutContext.Provider value={box}>
        <div className="fixed inset-0 flex items-center justify-center overflow-hidden bg-[#04110A]">
          <div
            style={{ width: box.asideWidth }}
            className="relative h-full shrink-0 overflow-hidden"
          >
            {aside}
          </div>
          <div
            style={{ width: STAGE_W * box.scale, height: STAGE_H * box.scale }}
            className="relative shrink-0 overflow-hidden shadow-[-12px_0_40px_rgba(0,0,0,0.45)]"
          >
            {stage}
          </div>
        </div>
      </LayoutContext.Provider>
    )
  }

  return (
    <LayoutContext.Provider value={box}>
      <div className="fixed inset-0 flex items-center justify-center overflow-hidden bg-black">
        {stage}
      </div>
    </LayoutContext.Provider>
  )
}
