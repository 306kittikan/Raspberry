import React from 'react'
import { useKiosk } from '../state/KioskProvider'

const VARIANTS = {
  primary:
    'bg-brand-700 text-white border-2 border-brand-700 active:bg-brand-800 disabled:bg-brand-200 disabled:border-brand-200 disabled:text-ink-mute',
  secondary:
    'bg-white text-brand-800 border-2 border-brand-300 active:bg-brand-50 disabled:text-ink-mute disabled:border-brand-100',
  danger:
    'bg-danger-600 text-white border-2 border-danger-600 active:bg-danger-700 disabled:bg-danger-100 disabled:border-danger-100',
  outlineDanger:
    'bg-white text-danger-700 border-2 border-danger-600 active:bg-danger-50 disabled:text-ink-mute disabled:border-brand-100',
  dark: 'bg-brand-900 text-white border-2 border-brand-900 active:bg-black',
  ghost: 'bg-transparent text-brand-800 border-2 border-transparent active:bg-brand-100',
}

const SIZES = {
  md: 'min-h-[88px] px-8 text-body font-semibold rounded-[22px]',
  lg: 'min-h-[112px] px-10 text-body-lg font-semibold rounded-[26px]',
  xl: 'min-h-[140px] px-12 text-h3 font-bold rounded-[30px]',
}

/** ปุ่มมาตรฐาน: เป้าแตะไม่ต่ำกว่า 72×72px และยุบลงทันทีเมื่อกด */
export function Button({
  children,
  variant = 'primary',
  size = 'lg',
  className = '',
  icon: Icon,
  ...rest
}) {
  return (
    <button
      type="button"
      className={`press tap inline-flex items-center justify-center gap-4 ${SIZES[size]} ${VARIANTS[variant]} disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
      {...rest}
    >
      {Icon ? <Icon className="h-10 w-10 shrink-0" /> : null}
      {children}
    </button>
  )
}

export function Panel({ children, className = '' }) {
  return <div className={`card p-10 ${className}`}>{children}</div>
}

export function SectionTitle({ children, right }) {
  return (
    <div className="mb-5 flex items-end justify-between">
      <h2 className="text-h3 font-bold text-brand-900">{children}</h2>
      {right}
    </div>
  )
}

/** ข้อความกำกับความสดของข้อมูล ต้องมีทุกหน้าที่แสดงตารางเรียน/กำหนดสอบ */
export function UpdatedAt({ className = '' }) {
  const { dataUpdatedLabel, hasSyntheticSchedule } = useKiosk()
  if (!dataUpdatedLabel && !hasSyntheticSchedule) return null
  return (
    <div className={`leading-snug ${className}`}>
      {dataUpdatedLabel ? (
        <p className="text-[22px] text-ink-mute">ข้อมูลอัปเดตล่าสุด: {dataUpdatedLabel}</p>
      ) : null}
      {/* ตราบใดที่ยังไม่ได้รับตารางเรียนจริงจากสาขา ต้องบอกผู้ใช้ตรง ๆ
          ไม่ให้เข้าใจผิดว่าเป็นตารางเรียนของตนเองจริง ๆ */}
      {hasSyntheticSchedule ? (
        <p className="mt-1 inline-flex items-center gap-2 rounded-full border-2 border-alert-100 bg-alert-50 px-4 py-1 text-[20px] font-semibold text-alert-900">
          ตารางเรียนเป็นข้อมูลตัวอย่าง ยังไม่ใช่ตารางจริง
        </p>
      ) : null}
    </div>
  )
}

export function EmptyState({ icon: Icon, title, detail, children }) {
  return (
    <div className="flex flex-col items-center rounded-[28px] border-2 border-dashed border-brand-200 bg-white px-10 py-14 text-center">
      {Icon ? <Icon className="mb-6 h-20 w-20 text-brand-400" /> : null}
      <p className="text-h3 font-bold text-brand-900">{title}</p>
      {detail ? <p className="mt-4 max-w-[760px] text-body text-ink-soft">{detail}</p> : null}
      {children ? <div className="mt-8">{children}</div> : null}
    </div>
  )
}
