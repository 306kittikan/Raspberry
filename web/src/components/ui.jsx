import React from 'react'
import { useKiosk } from '../state/KioskProvider'

// ปุ่มหลักใช้ไล่สีอ่อน ๆ บวกเงา แทนสีทึบที่มีกรอบหนา
// ทำให้เห็นว่ากดได้จากรูปทรง ไม่ต้องอาศัยเส้นขอบ
const VARIANTS = {
  primary:
    'bg-gradient-to-b from-brand-600 to-brand-700 text-white shadow-raise ' +
    'active:from-brand-700 active:to-brand-800 ' +
    'disabled:from-brand-200 disabled:to-brand-200 disabled:text-ink-mute disabled:shadow-none',
  secondary:
    'bg-white text-brand-800 shadow-card ring-1 ring-brand-200/70 ' +
    'active:bg-brand-50 disabled:text-ink-mute disabled:shadow-none',
  danger:
    'bg-gradient-to-b from-danger-600 to-danger-700 text-white shadow-raise ' +
    'active:from-danger-700 active:to-danger-700 ' +
    'disabled:from-danger-100 disabled:to-danger-100 disabled:shadow-none',
  outlineDanger:
    'bg-white text-danger-700 shadow-card ring-1 ring-danger-600/40 active:bg-danger-50',
  dark: 'bg-gradient-to-b from-brand-800 to-brand-900 text-white shadow-hero active:from-brand-900 active:to-black',
  ghost: 'bg-transparent text-brand-800 active:bg-brand-100',
}

const SIZES = {
  md: 'min-h-[88px] px-8 text-body font-semibold rounded-xl2',
  lg: 'min-h-[112px] px-10 text-body-lg font-semibold rounded-[24px]',
  xl: 'min-h-[140px] px-12 text-h3 font-bold rounded-xl3',
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
  const { dataUpdatedLabel, hasSyntheticSchedule, scheduleFromRegistrar } = useKiosk()
  if (!dataUpdatedLabel && !hasSyntheticSchedule && !scheduleFromRegistrar) return null
  return (
    <div className={`leading-snug ${className}`}>
      {dataUpdatedLabel ? (
        <p className="text-[22px] text-ink-mute">ข้อมูลอัปเดตล่าสุด: {dataUpdatedLabel}</p>
      ) : null}
      {/* ตราบใดที่ยังไม่ได้รับตารางเรียนจริงจากสาขา ต้องบอกผู้ใช้ตรง ๆ
          ไม่ให้เข้าใจผิดว่าเป็นตารางเรียนของตนเองจริง ๆ */}
      {/* ตารางที่ดึงสดจากระบบทะเบียนไม่ได้ถูกบันทึกไว้ในตู้
          บอกผู้ใช้ตรง ๆ เพราะเป็นข้อมูลของเขา เขาควรรู้ว่าตู้เก็บอะไรไว้บ้าง */}
      {scheduleFromRegistrar ? (
        <p className="mt-1 inline-flex items-center gap-2 rounded-full bg-brand-50 px-4 py-1 text-[20px] font-semibold text-brand-800 ring-1 ring-brand-200">
          ดึงสดจากระบบทะเบียน · ตู้ไม่ได้เก็บตารางเรียนของคุณไว้
        </p>
      ) : null}
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
    <div className="flex flex-col items-center rounded-xl3 border-2 border-dashed border-brand-200 bg-white/70 px-10 py-14 text-center">
      {Icon ? <Icon className="mb-6 h-20 w-20 text-brand-400" /> : null}
      <p className="text-h3 font-bold text-brand-900">{title}</p>
      {detail ? <p className="mt-4 max-w-[760px] text-body text-ink-soft">{detail}</p> : null}
      {children ? <div className="mt-8">{children}</div> : null}
    </div>
  )
}
