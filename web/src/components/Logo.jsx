import React from 'react'

/**
 * ตราสัญลักษณ์ของสาขา
 *
 * โลโก้ตัวจริงเป็นแนวนอน มีข้อความ COMPUTER SCIENCE · Maejo University อยู่ในภาพ
 * จึงตัดเป็นตราจัตุรัสไม่ได้ เพราะข้อความพาดทับวง C อยู่ ตัดแล้วจะเห็นตัวอักษรขาดครึ่ง
 * ทุกที่ที่ใช้จึงต้องเผื่อพื้นที่แนวนอนให้พอ
 *
 * ความสูงคือสิ่งที่กำหนดขนาด ส่วนความกว้างปล่อยให้ยืดตามสัดส่วนเอง
 * ถ้ากำหนดความกว้างด้วยจะเสี่ยงภาพบี้ เพราะพื้นที่แต่ละหน้าจอไม่เท่ากัน
 */
export default function Logo({ height = 72, className = '', title = true }) {
  return (
    <img
      src="/brand/csmju-logo.png"
      alt={title ? 'สาขาวิชาวิทยาการคอมพิวเตอร์ มหาวิทยาลัยแม่โจ้' : ''}
      style={{ height }}
      className={`w-auto shrink-0 select-none ${className}`}
      draggable={false}
    />
  )
}
